"""
消息总线 —— Agent 间直接通信。

设计来自 Claude Code Agent Teams：
  - 每个 agent 一个 inbox.jsonl 文件
  - 支持 direct（一对一）/ broadcast（全员）/ lead（汇报给 lead）
  - 消息带 TTL 自动过期
  - dispatch 时把未读消息注入 agent prompt

这就是 Claude Code 的 mailbox 机制的核心——文件系统就是消息队列。
"""

from __future__ import annotations
import json
import os
import time
from datetime import datetime
from pathlib import Path
import threading
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class Message:
    id: str
    channel: str          # "direct" | "broadcast" | "lead"
    from_agent: str
    to_agent: Optional[str]  # None for broadcast
    subject: str
    body: str
    created_at: str = ""
    status: str = "pending"   # "pending" | "delivered" | "expired"
    ttl_seconds: int = 86400  # 24h default

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.id:
            self.id = f"msg_{int(time.time()*1000)}_{hash(self.body) % 10000:04d}"

    @classmethod
    def create(cls, channel: str, from_agent: str, subject: str, body: str,
               to_agent: str = None, ttl_seconds: int = 86400) -> "Message":
        """便捷构造方法——不需要手动传 id 和 created_at"""
        return cls(
            id="",
            channel=channel,
            from_agent=from_agent,
            to_agent=to_agent,
            subject=subject,
            body=body,
            ttl_seconds=ttl_seconds,
        )


class MessageBus:
    """
    基于文件系统的 Agent 消息总线。
    
    用法：
        bus = MessageBus(base_dir=".orchestry/messages")
        
        # agent-a 给 agent-b 发消息
        bus.send(Message(
            channel="direct",
            from_agent="planner",
            to_agent="builder-1",
            subject="需求变更",
            body="第三个任务需要加错误处理",
        ))
        
        # lead 广播给全员
        bus.send(Message(
            channel="broadcast",
            from_agent="lead",
            to_agent=None,
            subject="全体注意",
            body="数据库 schema 已更新，请重新读取",
        ))
        
        # builder 读取自己的未读消息
        messages = bus.read_inbox("builder-1")
        for msg in messages:
            print(f"[{msg.from_agent}] {msg.subject}: {msg.body}")
    """
    
    def __init__(self, base_dir: str = ".orchestry/messages"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
    
    def _inbox_path(self, agent_name: str) -> Path:
        return self.base_dir / f"{agent_name}.jsonl"
    
    def send(self, message: Message):
        """发送消息——追加到目标 agent 的 inbox 文件（线程安全）"""
        targets = []
        
        if message.channel == "direct":
            if message.to_agent:
                targets.append(message.to_agent)
        elif message.channel == "broadcast":
            # 给所有有 inbox 的 agent 发
            targets = self._all_agents()
            # 排除发送者自己
            targets = [t for t in targets if t != message.from_agent]
        elif message.channel == "lead":
            targets.append("lead")
        
        with self._lock:
            for target in targets:
                inbox = self._inbox_path(target)
                # 确保目标 agent 的 inbox 存在
                if not inbox.exists():
                    inbox.touch()
                
                with open(inbox, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(message), ensure_ascii=False) + "\n")
    
    def read_inbox(self, agent_name: str, mark_delivered: bool = True) -> list[Message]:
        """读取 agent 的未读消息（线程安全）"""
        inbox = self._inbox_path(agent_name)
        if not inbox.exists():
            return []
        
        with self._lock:
            messages = []
            all_lines = []
            
            with open(inbox, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        msg = Message(**data)
                        
                        # 检查是否过期
                        created_ts = datetime.fromisoformat(msg.created_at).timestamp()
                        if time.time() - created_ts > msg.ttl_seconds:
                            msg.status = "expired"
                            continue  # 丢弃过期消息
                        
                        if msg.status == "pending":
                            messages.append(msg)
                            if mark_delivered:
                                msg.status = "delivered"
                        
                        all_lines.append(json.dumps(asdict(msg), ensure_ascii=False))
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue
            
            # 回写（更新 status）
            if mark_delivered and messages:
                with open(inbox, "w", encoding="utf-8") as f:
                    for line in all_lines:
                        f.write(line + "\n")
        
        return messages
    
    def _all_agents(self) -> list[str]:
        """列出所有有 inbox 的 agent"""
        agents = []
        for f in self.base_dir.glob("*.jsonl"):
            agents.append(f.stem)
        return agents
    
    def format_messages_for_prompt(self, agent_name: str) -> str:
        """格式化未读消息，用于注入 agent prompt"""
        messages = self.read_inbox(agent_name, mark_delivered=True)
        
        if not messages:
            return ""
        
        parts = ["【来自其他 Agent 的消息】"]
        for msg in messages:
            if msg.channel == "broadcast":
                parts.append(f"📢 [全员广播] {msg.from_agent}: {msg.subject}")
            else:
                parts.append(f"💬 {msg.from_agent} → 你: {msg.subject}")
            parts.append(f"   {msg.body}")
        parts.append("")
        
        return "\n".join(parts)
    
    def clear_inbox(self, agent_name: str):
        """清空 agent 的 inbox"""
        inbox = self._inbox_path(agent_name)
        if inbox.exists():
            inbox.write_text("")
    
    def clear_all(self):
        """清空所有 inbox"""
        for f in self.base_dir.glob("*.jsonl"):
            f.write_text("")
