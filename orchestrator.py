"""
编排引擎 —— 核心调度器。

工作流程：
  1. 用户给一个 Goal（目标）
  2. planner 拆成子任务列表
  3. 按依赖排序，逐个派发给 builder
  4. 每个 builder 完成后走 reviewer
  5. reviewer 通过 → done，不通过 → 打回重做
  6. 全部 done → 输出最终结果

GLM-5.1 适配策略：
  - 编排逻辑全在 Python 代码里，不依赖模型的 tool_call
  - 模型只负责"读 prompt → 输出文本"
  - 重试机制处理 GLM 的偶尔抽风
  - prompt 里重复关键指令对抗 GLM 不听话
"""

from __future__ import annotations
import json
import re
import time
from datetime import datetime
from typing import Optional

from task import Task, TaskStatus, can_transition, is_blocked, is_dispatchable
from agents import AgentRole, PLANNER, BUILDER, REVIEWER, ROLE_MAP
from llm_client import call_glm


# ============================================================
# Review 判定
# ============================================================

def _parse_review_verdict(review_text: str) -> str:
    """从 review 结果中提取判定。返回 'approve' / 'reject'。
    
    规则：只看文本开头或首个独立行的关键词，
    避免正文中出现的 "APPROVE"/"通过" 被误判。
    """
    # 取前 200 字符 + 首行，避免被正文干扰
    head = review_text.strip()[:200].lower()
    first_line = review_text.strip().split("\n")[0].strip().lower()
    
    approve_kw = ["approve", "通过", "✅", "accept", "approved", "合格", "确认"]
    reject_kw  = ["reject", "拒绝", "不通过", "❌", "deny", "denied", "需修改", "需补充"]
    
    # 先检查首行（最权威的信号）
    for kw in reject_kw:
        if kw in first_line:
            return "reject"
    for kw in approve_kw:
        if kw in first_line:
            return "approve"
    
    # 再检查头部区域
    for kw in reject_kw:
        if kw in head:
            return "reject"
    for kw in approve_kw:
        if kw in head:
            return "approve"
    
    # 默认 reject（宁可多改一次，也不要放过低质量输出）
    return "reject"


# ============================================================
# Planner 输出解析器
# ============================================================

def parse_plan(plan_text: str) -> list[dict]:
    """
    解析 planner 的输出为结构化任务列表。
    
    预期格式：
    TASK: xxx
    DESC: xxx
    ROLE: builder
    PRIORITY: 2
    DEPS: 1,3
    """
    tasks = []
    # 按空行分块
    blocks = re.split(r'\n\s*\n', plan_text.strip())
    
    current_task = {}
    for block in blocks:
        lines = block.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('TASK:') or line.startswith('任务') or line.startswith('- 任务'):
                if current_task.get('title'):
                    tasks.append(current_task)
                current_task = {
                    'title': re.sub(r'^(TASK:\s*|任务\d*[:：]\s*|-\s*任务\d*[:：]\s*)', '', line).strip(),
                    'description': '',
                    'role': 'builder',
                    'priority': 2,
                    'deps': [],
                }
            elif line.startswith('DESC:') or line.startswith('描述'):
                current_task['description'] = re.sub(r'^(DESC:\s*|描述[:：]\s*)', '', line).strip()
            elif line.startswith('ROLE:') or line.startswith('角色') or line.startswith('执行者'):
                role_str = re.sub(r'^(ROLE:\s*|角色[:：]\s*|执行者[:：]\s*)', '', line).strip().lower()
                if 'review' in role_str:
                    current_task['role'] = 'reviewer'
                else:
                    current_task['role'] = 'builder'
            elif line.startswith('PRIORITY:') or line.startswith('优先级'):
                try:
                    current_task['priority'] = int(re.sub(r'\D', '', line))
                except ValueError:
                    current_task['priority'] = 2
            elif line.startswith('DEPS:') or line.startswith('依赖'):
                deps_str = re.sub(r'^(DEPS:\s*|依赖[:：]\s*)', '', line).strip()
                if deps_str.lower() not in ('none', '无', '', '无依赖'):
                    current_task['deps'] = [d.strip() for d in re.split(r'[,，、]', deps_str) if d.strip()]
    
    if current_task.get('title'):
        tasks.append(current_task)
    
    return tasks


# ============================================================
# 编排引擎
# ============================================================

class Orchestrator:
    """
    简化版多 Agent 编排引擎。
    
    用法：
        engine = Orchestrator(model="glm-5.1")
        result = engine.run("写一个学生成绩分析报告", context="数据文件：scores.csv，50名学生")
    """
    
    def __init__(
        self,
        model: str = "glm-5.1",
        max_retries_per_task: int = 2,
        verbose: bool = True,
        auto_approve: bool = False,  # True = 跳过 reviewer
    ):
        self.model = model
        self.max_retries = max_retries_per_task
        self.verbose = verbose
        self.auto_approve = auto_approve
        self.tasks: dict[str, Task] = {}
        self.run_log: list[dict] = []
    
    def _log(self, msg: str):
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"  [{timestamp}] {msg}")
    
    def _call_agent(self, role: AgentRole, task: Task, context: str = "") -> str:
        """调用 agent 执行任务"""
        prompt = role.task_prompt_template.format(
            task_title=task.title,
            task_description=task.description,
            context=context or "(无额外上下文)",
            result=task.result or "",
        )
        
        self._log(f"→ 调用 {role.name} 处理: {task.title[:40]}...")
        response = call_glm(
            system_prompt=role.system_prompt,
            user_prompt=prompt,
            model=self.model,
        )
        self._log(f"← {role.name} 返回 {len(response)} 字符")
        
        return response
    
    def _get_context_for_task(self, task: Task) -> str:
        """收集依赖任务的输出作为上下文"""
        if not task.depends_on:
            return ""
        
        parts = []
        for dep_id in task.depends_on:
            dep = self.tasks.get(dep_id)
            if dep and dep.result:
                parts.append(f"【{dep.title} 的结果】\n{dep.result[:2000]}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _resolve_deps(self, plan: list[dict]) -> list[dict]:
        """把依赖编号（1,2,3）转成实际的 task_id"""
        # 先给每个任务分配 ID
        id_map = {}
        for i, p in enumerate(plan):
            task_id = f"t{i+1}"
            id_map[str(i+1)] = task_id
            p['_id'] = task_id
        
        # 再把 deps 里的编号替换成 ID
        for p in plan:
            resolved = []
            for dep in p.get('deps', []):
                if dep in id_map:
                    resolved.append(id_map[dep])
            p['deps'] = resolved
        
        return plan
    
    def _topological_sort(self) -> list[Task]:
        """拓扑排序：按依赖关系确定执行顺序"""
        sorted_tasks = []
        visited = set()
        visiting = set()
        
        def visit(task_id: str):
            if task_id in visited:
                return
            if task_id in visiting:
                return  # 循环依赖，跳过
            visiting.add(task_id)
            task = self.tasks.get(task_id)
            if task:
                for dep_id in task.depends_on:
                    visit(dep_id)
                visited.add(task_id)
                sorted_tasks.append(task)
            visiting.discard(task_id)
        
        for task_id in self.tasks:
            visit(task_id)
        
        # 按优先级排序同层级的任务
        return sorted_tasks
    
    def run(self, goal: str, context: str = "") -> dict:
        """
        运行完整编排流程。
        
        返回：
        {
            "status": "success" | "partial" | "failed",
            "tasks": [...],
            "final_output": str,
            "log": [...],
        }
        """
        start_time = time.time()
        self._log(f"🎯 开始编排: {goal[:60]}...")
        
        # ========== Phase 1: Planning ==========
        self._log("📋 Phase 1: Planning")
        plan_task = Task(
            id="plan",
            title=goal,
            description=context or "",
        )
        
        plan_text = self._call_agent(PLANNER, plan_task, context)
        plan = parse_plan(plan_text)
        
        if not plan:
            self._log("❌ 规划失败：未能解析出有效任务列表")
            return {
                "status": "failed",
                "error": "planner 未输出有效任务",
                "plan_raw": plan_text,
                "final_output": "",
                "tasks": [],
                "log": self.run_log,
                "duration_s": time.time() - start_time,
            }
        
        self._log(f"✅ 规划完成：{len(plan)} 个子任务")
        
        # 解决依赖引用
        plan = self._resolve_deps(plan)
        
        # 创建 Task 对象
        for p in plan:
            task = Task(
                id=p['_id'],
                title=p['title'],
                description=p.get('description', ''),
                priority=p.get('priority', 2),
                assignee=p.get('role', 'builder'),
                depends_on=p.get('deps', []),
            )
            self.tasks[task.id] = task
            self._log(f"  📌 {task.id}: {task.title} (角色={task.assignee}, 依赖={task.depends_on})")
        
        # ========== Phase 2: Execution ==========
        self._log("🔨 Phase 2: Execution")
        sorted_tasks = self._topological_sort()
        
        completed = 0
        failed = 0
        
        for task in sorted_tasks:
            self._log(f"\n--- 处理任务 {task.id}: {task.title[:40]} ---")
            
            # 检查依赖
            if is_blocked(task, self.tasks):
                self._log(f"  ⏸ 跳过: 依赖未完成")
                task.status = TaskStatus.FAILED
                failed += 1
                continue
            
            task.status = TaskStatus.IN_PROGRESS
            context_for_task = self._get_context_for_task(task)
            
            # 确定执行角色
            role = REVIEWER if task.assignee == 'reviewer' else BUILDER
            
            for attempt in range(self.max_retries + 1):
                try:
                    result = self._call_agent(role, task, context_for_task)
                    task.result = result
                    task.attempts = attempt + 1
                    
                    # ========== Phase 3: Review ==========
                    if self.auto_approve:
                        task.status = TaskStatus.DONE
                        self._log(f"  ✅ 自动通过")
                    else:
                        task.status = TaskStatus.REVIEWING
                        review_result = self._call_agent(REVIEWER, task, context_for_task)
                        
                        if _parse_review_verdict(review_result) == "approve":
                            task.status = TaskStatus.DONE
                            self._log(f"  ✅ Review 通过")
                        else:
                            # 打回
                            task.feedback = review_result
                            if attempt < self.max_retries:
                                task.status = TaskStatus.RETRYING
                                self._log(f"  🔄 Review 不通过，重试 ({attempt+1}/{self.max_retries})")
                                # 把 reviewer 的反馈注入上下文
                                context_for_task = (
                                    f"{context_for_task}\n\n"
                                    f"【审查反馈（请根据此反馈修改你的输出）】\n{review_result}"
                                ) if context_for_task else f"【审查反馈】\n{review_result}"
                                continue
                            else:
                                task.status = TaskStatus.FAILED
                                self._log(f"  ❌ 超过最大重试次数")
                    
                    break
                    
                except Exception as e:
                    self._log(f"  ⚠️ 调用失败: {e}")
                    if attempt < self.max_retries:
                        time.sleep(3)
                    else:
                        task.status = TaskStatus.FAILED
                        task.result = f"ERROR: {e}"
            
            if task.status == TaskStatus.DONE:
                completed += 1
            elif task.status == TaskStatus.FAILED:
                failed += 1
            
            self.run_log.append({
                "task_id": task.id,
                "title": task.title,
                "status": task.status.value,
                "attempts": task.attempts,
                "result_length": len(task.result) if task.result else 0,
            })
        
        # ========== 汇总 ==========
        duration = time.time() - start_time
        total = len(self.tasks)
        status = "success" if completed == total else ("partial" if completed > 0 else "failed")
        
        self._log(f"\n{'='*50}")
        self._log(f"🏁 编排完成: {completed}/{total} 任务成功, {failed} 失败")
        self._log(f"⏱ 耗时: {duration:.1f}s")
        
        # 拼装最终输出
        final_parts = []
        for task in sorted_tasks:
            if task.status == TaskStatus.DONE and task.result:
                final_parts.append(f"## {task.title}\n{task.result}")
        final_output = "\n\n---\n\n".join(final_parts)
        
        return {
            "status": status,
            "completed": completed,
            "total": total,
            "failed": failed,
            "final_output": final_output,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status.value,
                    "assignee": t.assignee,
                    "attempts": t.attempts,
                    "has_result": bool(t.result and not t.result.startswith("ERROR")),
                    "feedback": t.feedback,
                }
                for t in self.tasks.values()
            ],
            "log": self.run_log,
            "duration_s": round(duration, 1),
        }
