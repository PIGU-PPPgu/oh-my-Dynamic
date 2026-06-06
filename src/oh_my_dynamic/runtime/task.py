"""
Task 状态机 —— 多 Agent 编排的基础。

状态流转：
  todo → in_progress → review → done
    ↘ retrying → in_progress
      ↘ failed (超过最大重试)
  review → todo (被打回)
  * → cancelled

设计原则（来自 ORCH 源码）：
  - 纯函数，零副作用
  - 所有转换必须显式校验
  - 终态不自动流转
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEWING = "review"
    DONE = "done"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


# 合法状态转换表
VALID_TRANSITIONS: dict[TaskStatus, list[TaskStatus]] = {
    TaskStatus.TODO:        [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
    TaskStatus.IN_PROGRESS: [TaskStatus.REVIEWING, TaskStatus.RETRYING, TaskStatus.FAILED, TaskStatus.CANCELLED],
    TaskStatus.RETRYING:    [TaskStatus.IN_PROGRESS, TaskStatus.FAILED, TaskStatus.CANCELLED],
    TaskStatus.REVIEWING:   [TaskStatus.DONE, TaskStatus.TODO, TaskStatus.CANCELLED],
    TaskStatus.DONE:        [],
    TaskStatus.FAILED:      [TaskStatus.TODO, TaskStatus.RETRYING],
    TaskStatus.CANCELLED:   [TaskStatus.TODO],
}

TERMINAL_STATUSES = {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED}


@dataclass
class Task:
    id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.TODO
    priority: int = 2                # 1=最高, 4=最低
    assignee: Optional[str] = None   # agent role name
    depends_on: list[str] = field(default_factory=list)  # task IDs
    max_attempts: int = 3
    attempts: int = 0
    result: Optional[str] = None     # agent 输出
    feedback: Optional[str] = None   # reviewer 打回原因
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


def can_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, [])


def is_terminal(status: TaskStatus) -> bool:
    return status in TERMINAL_STATUSES


def is_dispatchable(status: TaskStatus) -> bool:
    """可以被派发给 agent 执行的状态"""
    return status in {TaskStatus.TODO, TaskStatus.RETRYING}


def is_blocked(task: Task, all_tasks: dict[str, Task]) -> bool:
    """检查依赖是否全部完成"""
    for dep_id in task.depends_on:
        dep = all_tasks.get(dep_id)
        if dep and dep.status != TaskStatus.DONE:
            return True
    return False
