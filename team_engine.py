"""
Team Engine —— 并行多 Agent 团队。

设计来自 Claude Code Agent Teams：
  - TeamCreate → 创建 team 目录 + 配置
  - TaskCreate → 创建共享任务列表（JSON 文件）
  - 并行 spawn 多个 agent 进程
  - agent 通过 MessageBus 互相通信
  - 文件锁防竞态（两个 agent 不能 claim 同一个 task）

核心区别 vs 上一版 orchestrator：
  - 上一版：串行执行（一个接一个）
  - 这一版：并行执行（多个同时跑），真正像 Claude Agent Teams
"""

from __future__ import annotations
import json
import os
import time
import fcntl
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed, Future

from task import Task, TaskStatus
from agents import AgentRole, PLANNER, BUILDER, REVIEWER, ROLE_MAP
from llm_client import call_glm
from message_bus import MessageBus, Message


# ============================================================
# Team 配置
# ============================================================

@dataclass
class TeamConfig:
    name: str
    description: str = ""
    created_at: str = ""
    lead_agent: str = "lead"
    max_parallel: int = 3         # 最大并行 agent 数
    auto_approve: bool = False    # 是否跳过 reviewer
    model: str = "glm-5.1"
    status: str = "active"        # active | paused | disbanded
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class TeamTask:
    """团队共享任务（存为 JSON 文件）"""
    id: str
    subject: str
    description: str
    status: str = "pending"      # pending | in_progress | completed | failed
    owner: str = ""              # claim 的 agent 名
    priority: int = 2
    depends_on: list = field(default_factory=list)
    result: str = ""
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.id:
            self.id = f"task_{uuid.uuid4().hex[:8]}"


# ============================================================
# Team Engine
# ============================================================

class TeamEngine:
    """
    并行多 Agent 团队引擎。
    
    用法：
        engine = TeamEngine("data-pipeline-team", max_parallel=3)
        engine.create_team("数据基座开发团队")
        engine.create_task("设计数据库 schema", "根据需求设计表结构...")
        engine.create_task("编写 ETL 脚本", "从 CSV 导入数据...", depends_on=["task_xxx"])
        engine.spawn_agent("architect", BUILDER)
        engine.spawn_agent("coder", BUILDER)
        engine.spawn_agent("qa", REVIEWER)
        result = engine.run()
    """
    
    def __init__(
        self,
        team_name: str,
        base_dir: str = ".orchestry",
        max_parallel: int = 3,
        model: str = "glm-5.1",
        auto_approve: bool = False,
        verbose: bool = True,
    ):
        self.team_name = team_name
        self.base_dir = Path(base_dir)
        self.team_dir = self.base_dir / "teams" / team_name
        self.task_dir = self.team_dir / "tasks"
        self.config_path = self.team_dir / "config.json"
        
        self.config = TeamConfig(
            name=team_name,
            max_parallel=max_parallel,
            model=model,
            auto_approve=auto_approve,
        )
        
        self.bus = MessageBus(str(self.base_dir / "messages"))
        self.agents: dict[str, AgentRole] = {}
        self._verbose = verbose
    
    def _log(self, msg: str):
        if self._verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] 🏠 {msg}")
    
    # ========== TeamCreate ==========
    
    def create_team(self, description: str = ""):
        """创建 team 目录结构（模仿 Claude Code 的 TeamCreate）"""
        self.team_dir.mkdir(parents=True, exist_ok=True)
        self.task_dir.mkdir(parents=True, exist_ok=True)
        self.config.description = description
        
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.config), f, ensure_ascii=False, indent=2)
        
        # 创建 lead 的 inbox
        self.bus._inbox_path("lead").touch()
        
        self._log(f"Team '{self.team_name}' 创建完成")
        self._log(f"  目录: {self.team_dir}")
        self._log(f"  最大并行: {self.config.max_parallel}")
    
    def delete_team(self):
        """清理 team（模仿 Claude Code 的 TeamDelete）"""
        import shutil
        if self.team_dir.exists():
            shutil.rmtree(self.team_dir)
        self.bus.clear_all()
        self._log(f"Team '{self.team_name}' 已清理")
    
    # ========== TaskCreate ==========
    
    def create_task(
        self,
        subject: str,
        description: str = "",
        priority: int = 2,
        depends_on: list[str] = None,
    ) -> TeamTask:
        """创建共享任务（存为 JSON 文件）"""
        task = TeamTask(
            id=f"task_{uuid.uuid4().hex[:8]}",
            subject=subject,
            description=description,
            priority=priority,
            depends_on=depends_on or [],
        )
        
        task_path = self.task_dir / f"{task.id}.json"
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(asdict(task), f, ensure_ascii=False, indent=2)
        
        self._log(f"  📌 任务创建: {task.id} - {subject[:40]}")
        return task
    
    def _load_tasks(self) -> list[TeamTask]:
        """从文件加载所有任务"""
        tasks = []
        if not self.task_dir.exists():
            return tasks
        for f in self.task_dir.glob("task_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                tasks.append(TeamTask(**data))
            except (json.JSONDecodeError, TypeError):
                continue
        return tasks
    
    def _save_task(self, task: TeamTask):
        """保存任务状态到文件"""
        task_path = self.task_dir / f"{task.id}.json"
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(asdict(task), f, ensure_ascii=False, indent=2)
    
    def _claim_task(self, task: TeamTask, agent_name: str) -> bool:
        """
        原子性 claim 任务——用文件锁防止竞态。
        这就是 Claude Code 的 task claiming 机制。
        """
        lock_path = self.task_dir / f"{task.id}.lock"
        
        try:
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # 重新读取最新状态
                task_path = self.task_dir / f"{task.id}.json"
                data = json.loads(task_path.read_text(encoding="utf-8"))
                current = TeamTask(**data)
                
                if current.status != "pending" or current.owner:
                    return False  # 已经被别人 claim 了
                
                # claim
                current.status = "in_progress"
                current.owner = agent_name
                self._save_task(current)
                return True
        except (IOError, OSError):
            return False
    
    def _find_available_task(self, agent_name: str) -> Optional[TeamTask]:
        """找到一个未被 claim、依赖已满足的任务"""
        tasks = self._load_tasks()
        completed_ids = {t.id for t in tasks if t.status == "completed"}
        
        candidates = [
            t for t in tasks
            if t.status == "pending"
            and not t.owner
            and all(dep in completed_ids for dep in t.depends_on)
        ]
        
        if not candidates:
            return None
        
        # 按优先级排序
        candidates.sort(key=lambda t: t.priority)
        return candidates[0]
    
    # ========== Spawn Agent ==========
    
    def spawn_agent(self, agent_name: str, role: AgentRole, system_prompt_extra: str = ""):
        """注册一个 agent 角色"""
        self.agents[agent_name] = role
        self.bus._inbox_path(agent_name).touch()
        self._log(f"  🤖 Agent '{agent_name}' 已注册 (角色: {role.name})")
    
    # ========== 并行执行核心 ==========
    
    def _run_single_agent(self, agent_name: str, max_idle_rounds: int = 30) -> dict:
        """
        单个 agent 的工作循环。
        
        这就是 Claude Code 里每个 teammate 做的事：
          1. 读 inbox 消息
          2. 从共享任务列表 claim 一个任务
          3. 执行任务
          4. 把结果写回任务文件
          5. 通过消息通知 lead
        
        Args:
            agent_name: agent 名称
            max_idle_rounds: 连续抢不到任务的最大空转轮数，超过后退出（默认 30 轮）
        """
        role = self.agents[agent_name]
        completed_tasks = []
        failed_tasks = []
        idle_rounds = 0
        
        self._log(f"  🚀 {agent_name} 开始工作 (max_idle={max_idle_rounds})")
        
        while True:
            # 1. 读消息
            messages = self.bus.read_inbox(agent_name)
            msg_context = ""
            if messages:
                msg_context = self.bus.format_messages_for_prompt(agent_name)
                for m in messages:
                    self._log(f"  📩 {agent_name} 收到消息: {m.subject}")
            
            # 2. Claim 任务
            task = self._find_available_task(agent_name)
            if not task:
                # 检查是否还有未完成的任务
                all_tasks = self._load_tasks()
                pending = [t for t in all_tasks if t.status in ("pending", "in_progress")]
                if not pending:
                    self._log(f"  ✅ {agent_name}: 所有任务完成，退出")
                    break
                else:
                    # 还有任务但依赖没满足，等一下
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        self._log(f"  ⏰ {agent_name}: 连续 {max_idle_rounds} 轮无任务可领，退出")
                        break
                    time.sleep(2)
                    continue
            
            # 尝试 claim
            if not self._claim_task(task, agent_name):
                idle_rounds += 1
                if idle_rounds >= max_idle_rounds:
                    self._log(f"  ⏰ {agent_name}: 连续 {max_idle_rounds} 轮 claim 失败，退出")
                    break
                time.sleep(1)
                continue
            
            self._log(f"  🔨 {agent_name} claim 了: {task.subject[:40]}")
            idle_rounds = 0  # 成功 claim，重置 idle 计数
            
            # 3. 收集依赖任务的输出作为上下文
            all_tasks = self._load_tasks()
            dep_context = ""
            for dep_id in task.depends_on:
                dep = next((t for t in all_tasks if t.id == dep_id), None)
                if dep and dep.result:
                    dep_context += f"\n【{dep.subject} 的结果】\n{dep.result[:2000]}\n"
            
            # 4. 执行
            full_context = f"{dep_context}\n{msg_context}".strip()
            prompt = role.task_prompt_template.format(
                task_title=task.subject,
                task_description=task.description,
                context=full_context or "(无额外上下文)",
                result="",
            )
            
            try:
                result = call_glm(
                    system_prompt=role.system_prompt,
                    user_prompt=prompt,
                    model=self.config.model,
                )
                
                # 5. Review（如果不 auto_approve 且是 builder 角色）
                if not self.config.auto_approve and role.name == "builder":
                    review_prompt = REVIEWER.task_prompt_template.format(
                        task_title=task.subject,
                        task_description=task.description,
                        context=dep_context,
                        result=result,
                    )
                    review_result = call_glm(
                        system_prompt=REVIEWER.system_prompt,
                        user_prompt=review_prompt,
                        model=self.config.model,
                    )
                    
                    from orchestrator import _parse_review_verdict
                    if _parse_review_verdict(review_result) == "reject":
                        # 通知 lead
                        self.bus.send(Message.create(
                            channel="lead",
                            from_agent=agent_name,
                            subject=f"任务被拒绝: {task.subject[:30]}",
                            body=review_result[:500],
                        ))
                        task.status = "failed"
                        task.result = f"REVIEW REJECTED:\n{review_result[:500]}\n\nORIGINAL:\n{result}"
                        self._save_task(task)
                        failed_tasks.append(task.id)
                        continue
                
                # 成功
                task.status = "completed"
                task.result = result
                self._save_task(task)
                completed_tasks.append(task.id)
                self._log(f"  ✅ {agent_name} 完成: {task.subject[:40]}")
                
                # 通知 lead
                self.bus.send(Message.create(
                    channel="lead",
                    from_agent=agent_name,
                    subject=f"任务完成: {task.subject[:30]}",
                    body=f"结果长度: {len(result)} 字符",
                ))
                
            except Exception as e:
                task.status = "failed"
                task.result = f"ERROR: {e}"
                self._save_task(task)
                failed_tasks.append(task.id)
                self._log(f"  ❌ {agent_name} 失败: {task.subject[:30]} - {e}")
        
        return {
            "agent": agent_name,
            "completed": len(completed_tasks),
            "failed": len(failed_tasks),
            "tasks_completed": completed_tasks,
            "tasks_failed": failed_tasks,
        }
    
    def run(self, goal: str = "", context: str = "") -> dict:
        """
        运行团队——Lead 先规划，然后并行执行。
        """
        start_time = time.time()
        self._log(f"🎯 Team '{self.team_name}' 启动")
        
        # ========== Lead Phase: 规划 ==========
        if goal:
            self._log("📋 Lead 规划中...")
            plan_prompt = PLANNER.task_prompt_template.format(
                task_title=goal,
                task_description=context or "",
                context="",
            )
            plan_text = call_glm(
                system_prompt=PLANNER.system_prompt,
                user_prompt=plan_prompt,
                model=self.config.model,
            )
            
            # 解析计划并创建任务
            from orchestrator import parse_plan
            plan = parse_plan(plan_text)
            
            if not plan:
                self._log("❌ 规划失败")
                return {"status": "failed", "error": "planner failed"}
            
            self._log(f"✅ 规划完成: {len(plan)} 个任务")
            
            # 解析依赖引用
            id_map = {}
            for i, p in enumerate(plan):
                task_id = f"task_{uuid.uuid4().hex[:8]}"
                id_map[str(i+1)] = task_id
                p['_id'] = task_id
            
            for p in plan:
                resolved_deps = [id_map[d] for d in p.get('deps', []) if d in id_map]
                self.create_task(
                    subject=p['title'],
                    description=p.get('description', ''),
                    priority=p.get('priority', 2),
                    depends_on=resolved_deps,
                )
        
        # ========== 并行执行 ==========
        self._log(f"🔨 并行执行开始 (max_parallel={self.config.max_parallel})")
        
        results = []
        with ThreadPoolExecutor(max_workers=self.config.max_parallel) as pool:
            futures = {
                pool.submit(self._run_single_agent, name): name
                for name in self.agents
            }
            
            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    result = future.result(timeout=300)  # 5分钟超时
                    results.append(result)
                except Exception as e:
                    results.append({
                        "agent": agent_name,
                        "error": str(e),
                        "completed": 0,
                        "failed": 0,
                    })
        
        # ========== 汇总 ==========
        tasks = self._load_tasks()
        completed = [t for t in tasks if t.status == "completed"]
        failed = [t for t in tasks if t.status == "failed"]
        
        duration = time.time() - start_time
        
        # 读 lead 的所有消息
        lead_messages = self.bus.read_inbox("lead", mark_delivered=False)
        
        self._log(f"\n{'='*50}")
        self._log(f"🏁 Team '{self.team_name}' 完成")
        self._log(f"  任务: {len(completed)}/{len(tasks)} 成功, {len(failed)} 失败")
        self._log(f"  耗时: {duration:.1f}s")
        self._log(f"  Agent 消息: {len(lead_messages)} 条")
        
        # 拼装最终输出
        final_parts = []
        for t in sorted(completed, key=lambda x: x.priority):
            if t.result and not t.result.startswith("ERROR"):
                final_parts.append(f"## {t.subject}\n{t.result}")
        
        return {
            "status": "success" if len(completed) == len(tasks) else "partial",
            "completed": len(completed),
            "total": len(tasks),
            "failed": len(failed),
            "final_output": "\n\n---\n\n".join(final_parts),
            "tasks": [
                {
                    "id": t.id,
                    "subject": t.subject,
                    "status": t.status,
                    "owner": t.owner,
                    "has_result": bool(t.result and not t.result.startswith("ERROR")),
                }
                for t in tasks
            ],
            "agents": results,
            "lead_messages": [
                {"from": m.from_agent, "subject": m.subject, "body": m.body[:200]}
                for m in lead_messages
            ],
            "duration_s": round(duration, 1),
        }
