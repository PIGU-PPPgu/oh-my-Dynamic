"""
Dynamic Replan —— 运行时动态调整计划。

Claude Code Dynamic Workflows 的核心：
  1. 不只在开头规划一次，执行过程中持续监控
  2. 发现问题（任务失败/需求变更/结果不对）→ 重新规划
  3. 新规划可以：添加任务、修改任务、删除任务、调整依赖
  4. 对抗验证：独立 agent 尝试反驳其他 agent 的结论

实现方式：
  - 每个 agent 完成后，Replanner 检查结果
  - 如果发现问题 → 生成新任务插入队列
  - 广播通知所有 agent 计划已更新
"""

from __future__ import annotations
import json
import time
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from llm_client import call_glm
from message_bus import MessageBus, Message
from agents import PLANNER, REVIEWER


REPLAN_PROMPT = """你是一个动态规划调整专家。

当前计划执行过程中发现了问题，你需要调整计划。

原始目标：{goal}
原始上下文：{context}

当前任务列表和执行状态：
{task_status}

发现的问题：
{issues}

请输出调整方案。每个调整用以下格式：

ACTION: add | modify | remove | reorder
TASK_ID: <现有任务ID，新增时写 new>
SUBJECT: <任务标题>
DESCRIPTION: <任务描述>
REASON: <为什么要做这个调整>
PRIORITY: <1-4>
DEPS: <依赖的任务ID，逗号分隔>

每个调整块之间用空行分隔。"""


@dataclass
class ReplanAction:
    action: str        # "add" | "modify" | "remove" | "reorder"
    task_id: str
    subject: str = ""
    description: str = ""
    reason: str = ""
    priority: int = 2
    deps: list = None
    
    def __post_init__(self):
        if self.deps is None:
            self.deps = []


def parse_replan(text: str) -> list[ReplanAction]:
    """解析 replan 输出"""
    actions = []
    blocks = text.strip().split("\n\n")
    
    for block in blocks:
        action = {}
        for line in block.strip().split("\n"):
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip().upper()
            val = val.strip()
            
            if key == "ACTION":
                action["action"] = val.lower()
            elif key == "TASK_ID":
                action["task_id"] = val
            elif key == "SUBJECT":
                action["subject"] = val
            elif key == "DESCRIPTION":
                action["description"] = val
            elif key == "REASON":
                action["reason"] = val
            elif key == "PRIORITY":
                try:
                    action["priority"] = int(val)
                except ValueError:
                    action["priority"] = 2
            elif key == "DEPS":
                action["deps"] = [d.strip() for d in val.split(",") if d.strip() and d.strip() != "none"]
        
        if action.get("action") and action.get("task_id"):
            actions.append(ReplanAction(
                action=action["action"],
                task_id=action["task_id"],
                subject=action.get("subject", ""),
                description=action.get("description", ""),
                reason=action.get("reason", ""),
                priority=action.get("priority", 2),
                deps=action.get("deps", []),
            ))
    
    return actions


class DynamicReplanner:
    """
    动态重规划器。
    
    在 TeamEngine 的执行循环中，每次有 agent 完成任务时：
      1. Replanner 检查结果是否有问题
      2. 如果有问题 → 生成调整方案
      3. 调整方案应用到共享任务列表
      4. 广播通知所有 agent
    
    用法（集成到 TeamEngine）：
        replanner = DynamicReplanner(model="glm-5.1")
        
        # agent 完成任务后检查
        issues = replanner.check_result(task, goal, all_tasks)
        if issues:
            adjustments = replanner.replan(goal, context, all_tasks, issues)
            apply_adjustments(adjustments)
            bus.broadcast("计划已更新，请重新读取任务列表")
    """
    
    def __init__(self, model: str = "glm-5.1", verbose: bool = True):
        self.model = model
        self._verbose = verbose
        self.replan_count = 0
    
    def _log(self, msg: str):
        if self._verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] 🔄 Replan: {msg}")
    
    def check_result(
        self,
        completed_task: dict,
        goal: str,
        all_tasks: list[dict],
    ) -> Optional[str]:
        """
        检查完成的任务结果是否有问题。
        返回问题描述，None 表示没问题。
        """
        result = completed_task.get("result", "")
        subject = completed_task.get("subject", "")
        
        # 基础检查
        if not result or result.startswith("ERROR"):
            return f"任务 '{subject}' 执行失败，需要重新安排或降级"
        
        if "REVIEW REJECTED" in result:
            return f"任务 '{subject}' 被 Reviewer 打回: {result[:300]}"
        
        # 语义检查——让模型判断结果是否合理
        check_prompt = f"""请检查以下任务的执行结果是否有明显问题。

原始目标：{goal}

任务：{subject}
执行结果：
{result[:2000]}

如果结果有明显问题（遗漏关键内容、逻辑错误、与目标不符），请简述问题。
如果结果基本合理，请回复 OK。"""
        
        try:
            check_result = call_glm(
                system_prompt="你是一个质量检查员，只关注明显问题，不要吹毛求疵。",
                user_prompt=check_prompt,
                model=self.model,
                temperature=0.1,  # 低温度，减少误判
            )
            
            if "OK" in check_result.upper() and len(check_result) < 50:
                return None
            
            # 模型认为有问题
            if len(check_result) > 20:
                return check_result
            
        except Exception as e:
            self._log(f"检查失败: {e}")
        
        return None
    
    def replan(
        self,
        goal: str,
        context: str,
        all_tasks: list[dict],
        issues: str,
    ) -> list[ReplanAction]:
        """
        根据发现的问题重新规划。
        """
        self.replan_count += 1
        self._log(f"第 {self.replan_count} 次重规划")
        
        # 构建当前任务状态
        task_status = ""
        for t in all_tasks:
            task_status += f"- {t.get('id', '?')}: [{t.get('status', '?')}] {t.get('subject', '?')}"
            if t.get('owner'):
                task_status += f" (执行者: {t['owner']})"
            task_status += "\n"
        
        prompt = REPLAN_PROMPT.format(
            goal=goal,
            context=context or "(无)",
            task_status=task_status,
            issues=issues,
        )
        
        try:
            result = call_glm(
                system_prompt="你是一个项目规划调整专家。根据执行中的问题动态调整计划。保持最小改动原则——能修补就不重做。",
                user_prompt=prompt,
                model=self.model,
            )
            
            actions = parse_replan(result)
            self._log(f"生成了 {len(actions)} 个调整动作")
            
            for a in actions:
                self._log(f"  {a.action} {a.task_id}: {a.subject[:30]} ({a.reason[:50]})")
            
            return actions
            
        except Exception as e:
            self._log(f"重规划失败: {e}")
            return []
    
    def check_and_replan(
        self,
        completed_task: dict,
        goal: str,
        context: str,
        all_tasks: list[dict],
    ) -> tuple[bool, list[ReplanAction]]:
        """
        一步到位：检查结果 + 如需重规划。
        
        返回 (needs_replan, adjustments)
        """
        issues = self.check_result(completed_task, goal, all_tasks)
        
        if issues:
            self._log(f"发现问题: {issues[:100]}")
            actions = self.replan(goal, context, all_tasks, issues)
            return True, actions
        
        return False, []


# ============================================================
# 对抗验证 —— Dynamic Workflows 的"独立反驳"机制
# ============================================================

ADVERSARIAL_PROMPT = """你是一个专门反驳的 Devil's Advocate。

以下是一个 agent 完成的任务及其结果。你的目标是找出其中的漏洞、错误或遗漏。

任务：{subject}
描述：{description}
执行结果：
{result}

请从以下角度审查：
1. 逻辑漏洞——结论是否有跳跃
2. 事实错误——数据、引用是否正确
3. 遗漏——是否有明显该覆盖但没覆盖的内容
4. 边界情况——是否考虑了异常/极端情况

如果找到了实质性问题，请详细描述。
如果结果确实可靠，请回复 VERIFIED。"""


class AdversarialVerifier:
    """
    对抗验证器——Claude Code Dynamic Workflows 的特色功能。
    
    独立的 agent 尝试反驳其他 agent 的结论。
    只有通过了对抗验证的结果才会被采纳。
    """
    
    def __init__(self, model: str = "glm-5.1", verbose: bool = True):
        self.model = model
        self._verbose = verbose
    
    def _log(self, msg: str):
        if self._verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] ⚔️ Adversarial: {msg}")
    
    def verify(self, task_subject: str, task_desc: str, result: str) -> dict:
        """
        对抗验证。
        
        返回：
        {
            "passed": bool,
            "issues": str,       # 发现的问题
            "severity": str,     # "none" | "minor" | "major"
        }
        """
        self._log(f"验证: {task_subject[:40]}")
        
        prompt = ADVERSARIAL_PROMPT.format(
            subject=task_subject,
            description=task_desc,
            result=result[:3000],
        )
        
        try:
            response = call_glm(
                system_prompt="你是一个严格的技术审查者。你的目标是确保结果真正可靠，而不是走形式。",
                user_prompt=prompt,
                model=self.model,
                temperature=0.2,
            )
            
            passed = "VERIFIED" in response.upper() and len(response) < 100
            severity = "none" if passed else ("minor" if len(response) < 200 else "major")
            
            if passed:
                self._log(f"✅ 通过验证")
            else:
                self._log(f"⚠️ 发现{severity}级问题: {response[:100]}")
            
            return {
                "passed": passed,
                "issues": response if not passed else "",
                "severity": severity,
            }
            
        except Exception as e:
            self._log(f"验证失败: {e}")
            return {
                "passed": True,  # 验证失败时默认通过，避免阻塞流程
                "issues": f"验证器异常: {e}",
                "severity": "none",
            }
