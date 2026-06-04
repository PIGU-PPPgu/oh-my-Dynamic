"""
Git Worktree 隔离 —— 每个 Agent 独立工作目录。

核心思想（来自 Anthropic 工程实践）：
  - 每个 Worker Agent 在独立的 git worktree 里工作
  - 互不干扰，完成后 PR merge 回主分支
  - 避免多个 Agent 同时修改同一个文件导致冲突

用法：
    worktree_mgr = WorktreeManager('/path/to/repo')
    
    # 为 agent 创建独立工作目录
    wt = worktree_mgr.create('data-collector')
    # → /path/to/repo/.worktrees/data-collector/
    
    # Agent 在 wt.path 里操作
    
    # 完成后合并
    worktree_mgr.merge('data-collector')
"""

from __future__ import annotations
import re
import subprocess
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


_AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_WORKTREE_CREATE_LOCK = threading.Lock()


def _validate_agent_name(agent_name: str) -> str:
    """Return a safe agent slug for branch and worktree paths."""
    if not _AGENT_NAME_RE.fullmatch(agent_name or ""):
        raise ValueError("agent_name 只能包含字母、数字、点、下划线、连字符，且长度不超过 64")
    if ".." in agent_name or agent_name.startswith("."):
        raise ValueError("agent_name 不能包含 '..' 或以点开头")
    return agent_name


@dataclass
class Worktree:
    """一个 git worktree 实例"""
    name: str
    path: str                          # 工作目录绝对路径
    branch: str                        # 分支名
    base_branch: str                   # 基于哪个分支创建的
    agent_id: str = ""                 # 绑定的 agent
    created_at: str = ""
    status: str = "active"             # active / merged / abandoned
    
    def is_active(self) -> bool:
        return self.status == "active" and Path(self.path).exists()


class WorktreeManager:
    """
    Git Worktree 管理器。
    
    在一个 git 仓库里为每个 Agent 创建独立工作目录。
    基于 git worktree 机制，真正的文件系统隔离。
    
    目录结构：
        repo/
        ├── .git/
        ├── .worktrees/           ← 工作目录在这里
        │   ├── agent-collector/
        │   ├── agent-analyzer/
        │   └── agent-writer/
        └── src/
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        self.worktrees_dir = self.repo_path / ".worktrees"
        self._state_file = self.worktrees_dir / "_state.json"
        self._worktrees: dict[str, Worktree] = {}
        
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"{repo_path} 不是 git 仓库")
        
        # 加载已有状态
        self._load_state()
    
    def _load_state(self):
        """加载 worktree 状态"""
        if self._state_file.exists():
            with open(self._state_file) as f:
                data = json.load(f)
            for name, wt_data in data.items():
                self._worktrees[name] = Worktree(**wt_data)
    
    def _save_state(self):
        """保存 worktree 状态"""
        self.worktrees_dir.mkdir(exist_ok=True)
        data = {}
        for name, wt in self._worktrees.items():
            data[name] = {
                "name": wt.name,
                "path": wt.path,
                "branch": wt.branch,
                "base_branch": wt.base_branch,
                "agent_id": wt.agent_id,
                "created_at": wt.created_at,
                "status": wt.status,
            }
        tmp_path = self._state_file.with_name(f"{self._state_file.name}.{uuid.uuid4().hex}.tmp")
        with open(tmp_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self._state_file)
    
    def _git(self, *args: str, cwd: Optional[str] = None) -> str:
        """执行 git 命令"""
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd or str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} 失败: {result.stderr.strip()}")
        return result.stdout.strip()
    
    def _get_current_branch(self) -> str:
        """获取当前分支名"""
        return self._git("branch", "--show-current") or "main"

    def _branch_exists(self, branch_name: str) -> bool:
        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0

    def _delete_branch_if_exists(self, branch_name: str) -> None:
        if self._branch_exists(branch_name):
            self._git("branch", "-D", branch_name)
    
    def create(
        self, 
        agent_name: str, 
        base_branch: Optional[str] = None,
        agent_id: str = "",
        branch_name: Optional[str] = None,
        worktree_path: Optional[str] = None,
    ) -> Worktree:
        """
        为一个 Agent 创建独立的 git worktree。
        
        Args:
            agent_name: Agent 名称（如 'collector', 'analyzer'）
            base_branch: 基于哪个分支创建（默认当前分支）
            agent_id: Agent 唯一 ID
        
        Returns:
            Worktree 实例
        """
        agent_name = _validate_agent_name(agent_name)

        if agent_name in self._worktrees and self._worktrees[agent_name].is_active():
            raise ValueError(f"Worktree '{agent_name}' 已存在")
        
        base = base_branch or self._get_current_branch()
        branch_name = branch_name or f"agent/{agent_name}"
        worktree_path = str(Path(worktree_path).resolve()) if worktree_path else str(self.worktrees_dir / agent_name)
        
        # 创建 worktrees 目录
        self.worktrees_dir.mkdir(exist_ok=True)

        with _WORKTREE_CREATE_LOCK:
            # 创建分支 + worktree
            try:
                self._git("branch", branch_name, base)
            except RuntimeError:
                if not self._branch_exists(branch_name):
                    raise
                # 分支可能已存在（之前 abandon 的），删除后重建。
                self._delete_branch_if_exists(branch_name)
                self._git("branch", branch_name, base)

            Path(worktree_path).parent.mkdir(parents=True, exist_ok=True)
            self._git("worktree", "add", worktree_path, branch_name)

            wt = Worktree(
                name=agent_name,
                path=worktree_path,
                branch=branch_name,
                base_branch=base,
                agent_id=agent_id,
                created_at=datetime.now().isoformat(),
                status="active",
            )

            self._load_state()
            self._worktrees[agent_name] = wt
            self._save_state()
        
        return wt
    
    def get(self, agent_name: str) -> Optional[Worktree]:
        """获取 worktree"""
        agent_name = _validate_agent_name(agent_name)
        return self._worktrees.get(agent_name)
    
    def list_active(self) -> list[Worktree]:
        """列出所有活跃的 worktree"""
        return [wt for wt in self._worktrees.values() if wt.is_active()]
    
    def merge(
        self, 
        agent_name: str, 
        commit_message: Optional[str] = None,
        strategy: str = "squash",
    ) -> str:
        """
        合并 Agent 的 worktree 回主分支。
        
        Args:
            agent_name: Agent 名称
            commit_message: 提交消息
            strategy: 'squash'（压缩合并）或 'merge'（保留历史）
        
        Returns:
            合并结果消息
        """
        agent_name = _validate_agent_name(agent_name)
        wt = self._worktrees.get(agent_name)
        if not wt or not wt.is_active():
            raise ValueError(f"Worktree '{agent_name}' 不存在或已失效")
        
        # 先在 worktree 里提交所有更改
        self._git("add", "-A", cwd=wt.path)
        try:
            self._git("commit", "-m", f"agent/{agent_name}: 工作完成", cwd=wt.path)
        except RuntimeError:
            pass  # 没有更改需要提交
        
        # 切回主分支
        target_branch = wt.base_branch
        
        if strategy == "squash":
            # Squash merge
            self._git("checkout", target_branch)
            self._git("merge", "--squash", wt.branch)
            msg = commit_message or f"Merge agent/{agent_name} (squash)"
            self._git("commit", "-m", msg)
        else:
            # 普通 merge
            self._git("checkout", target_branch)
            msg = commit_message or f"Merge agent/{agent_name}"
            self._git("merge", wt.branch, "-m", msg)
        
        # 清理 worktree
        self._git("worktree", "remove", wt.path, "--force")
        self._git("branch", "-d", wt.branch)
        
        wt.status = "merged"
        self._save_state()
        
        return f"已合并 {agent_name} → {target_branch} ({strategy})"
    
    def abandon(self, agent_name: str) -> str:
        """放弃一个 Agent 的工作，不合并"""
        agent_name = _validate_agent_name(agent_name)
        wt = self._worktrees.get(agent_name)
        if not wt:
            raise ValueError(f"Worktree '{agent_name}' 不存在")
        
        if Path(wt.path).exists():
            self._git("worktree", "remove", wt.path, "--force")
        
        try:
            self._delete_branch_if_exists(wt.branch)
        except RuntimeError:
            pass
        
        wt.status = "abandoned"
        self._save_state()
        
        return f"已放弃 {agent_name}"
    
    def cleanup(self):
        """清理所有已失效的 worktree"""
        for name, wt in list(self._worktrees.items()):
            if wt.status != "active":
                continue
            if not Path(wt.path).exists():
                wt.status = "abandoned"
        
        self._save_state()
    
    def diff_summary(self, agent_name: str) -> str:
        """查看 Agent 工作目录的变更摘要"""
        agent_name = _validate_agent_name(agent_name)
        wt = self._worktrees.get(agent_name)
        if not wt or not wt.is_active():
            return f"Worktree '{agent_name}' 不可用"
        
        try:
            return self._git("diff", "--stat", wt.base_branch, cwd=wt.path)
        except RuntimeError:
            return "无法获取 diff"
