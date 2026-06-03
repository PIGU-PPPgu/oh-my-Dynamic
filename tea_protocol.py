"""
TEA (Tool Evolution & Adaptation) Protocol
===========================================

Based on the AgentOrchestra paper (arXiv 2506.12508).

Agents can discover that their existing tools are insufficient, dynamically
create/improve tools, and manage tool versions with full rollback support.

Modules:
    - ToolVersion:  dataclass representing a single versioned tool snapshot
    - ToolRegistry:  persistent, thread-safe registry backed by JSON files
    - ToolEvolver:   LLM-driven tool analysis & evolution engine
    - TEAProtocol:   coordinator that hooks into a DAG execution lifecycle
"""

from __future__ import annotations

import json
import os
import re
import signal
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# ToolVersion
# ---------------------------------------------------------------------------

@dataclass
class ToolVersion:
    """Single versioned snapshot of a tool.

    Attributes:
        tool_id:        Stable identifier shared across all versions of a tool.
        version:        Semantic version string, e.g. ``'1.0.0'``.
        name:           Python-callable name of the tool function.
        description:    Human-readable description of what the tool does.
        code:           Raw Python source code (must define a function named *name*).
        created_at:     ISO-8601 timestamp (UTC).
        created_by:     Name of the agent that created this version.
        parent_version: The version string this one evolved from (``None`` for v1).
        change_reason:  Why this version was created / changed.
        test_results:   List of ``{'input': ..., 'output': ..., 'success': bool}`` dicts.
        status:         One of ``'active'``, ``'deprecated'``, ``'rolled_back'``.
    """

    tool_id: str
    version: str
    name: str
    description: str
    code: str
    created_at: str
    created_by: str
    parent_version: Optional[str]
    change_reason: str
    test_results: List[Dict] = field(default_factory=list)
    status: str = "active"

    # -- helpers ----------------------------------------------------------

    def to_dict(self) -> Dict:
        """Serialise to a plain dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ToolVersion":
        """Deserialise from a plain dict."""
        return cls(**data)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _bump_minor(version: str) -> str:
    """Bump the *minor* component of a semver string.

    >>> _bump_minor('1.2.3')
    '1.3.0'
    """
    parts = version.split(".")
    if len(parts) != 3:
        return "1.0.0"
    major, minor, _ = int(parts[0]), int(parts[1]), int(parts[2])
    return f"{major}.{minor + 1}.0"


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Persistent, thread-safe tool version registry.

    Storage layout::

        <storage_dir>/
            <tool_id>.json   →  {"versions": [ToolVersion.to_dict(), …]}

    Parameters:
        storage_dir: Directory where per-tool JSON files are stored.
    """

    def __init__(self, storage_dir: str = "./tea_tools") -> None:
        self.storage_dir = storage_dir
        self._lock = threading.Lock()
        os.makedirs(self.storage_dir, exist_ok=True)

    # -- internal persistence ---------------------------------------------

    def _path(self, tool_id: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", tool_id)
        return os.path.join(self.storage_dir, f"{safe}.json")

    def _load(self, tool_id: str) -> List[ToolVersion]:
        path = self._path(tool_id)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [ToolVersion.from_dict(v) for v in data.get("versions", [])]

    def _save(self, tool_id: str, versions: List[ToolVersion]) -> None:
        path = self._path(tool_id)
        payload = {"versions": [v.to_dict() for v in versions]}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    # -- public API -------------------------------------------------------

    def register(
        self,
        name: str,
        description: str,
        code: str,
        created_by: str,
    ) -> ToolVersion:
        """Register a **new** tool (auto version ``1.0.0``).

        Returns:
            The freshly created :class:`ToolVersion`.
        """
        tool_id = _new_id()
        tv = ToolVersion(
            tool_id=tool_id,
            version="1.0.0",
            name=name,
            description=description,
            code=code,
            created_at=_now_iso(),
            created_by=created_by,
            parent_version=None,
            change_reason="初始创建",
        )
        with self._lock:
            self._save(tool_id, [tv])
        return tv

    def evolve(
        self,
        tool_id: str,
        new_code: str,
        reason: str,
        created_by: str,
    ) -> ToolVersion:
        """Create a new **version** of an existing tool (bumps minor).

        Raises:
            FileNotFoundError: If *tool_id* is unknown.
        """
        with self._lock:
            versions = self._load(tool_id)
            if not versions:
                raise FileNotFoundError(f"工具 {tool_id} 不存在")

            # Determine latest version
            active = [v for v in versions if v.status == "active"]
            parent = active[-1] if active else versions[-1]

            # Deprecate previous active versions
            for v in versions:
                if v.status == "active":
                    v.status = "deprecated"

            new_ver = ToolVersion(
                tool_id=tool_id,
                version=_bump_minor(parent.version),
                name=parent.name,
                description=parent.description,
                code=new_code,
                created_at=_now_iso(),
                created_by=created_by,
                parent_version=parent.version,
                change_reason=reason,
            )
            versions.append(new_ver)
            self._save(tool_id, versions)
        return new_ver

    def get_active(self, tool_id: str) -> Optional[ToolVersion]:
        """Return the current **active** version, or ``None``."""
        with self._lock:
            versions = self._load(tool_id)
        for v in reversed(versions):
            if v.status == "active":
                return v
        return None

    def get_version(self, tool_id: str, version: str) -> Optional[ToolVersion]:
        """Return a specific version, or ``None``."""
        with self._lock:
            versions = self._load(tool_id)
        for v in versions:
            if v.version == version:
                return v
        return None

    def list_tools(self) -> List[ToolVersion]:
        """List the active version of every registered tool."""
        result: List[ToolVersion] = []
        with self._lock:
            for fname in os.listdir(self.storage_dir):
                if not fname.endswith(".json"):
                    continue
                tool_id = fname[: -len(".json")]
                versions = self._load(tool_id)
                for v in reversed(versions):
                    if v.status == "active":
                        result.append(v)
                        break
        return result

    def history(self, tool_id: str) -> List[ToolVersion]:
        """Return the full version history (oldest → newest)."""
        with self._lock:
            return self._load(tool_id)

    def rollback(self, tool_id: str, target_version: str) -> ToolVersion:
        """Roll back to a previous version.

        All currently-active versions are marked ``'rolled_back'`` and the
        *target_version* is re-activated (as a new version entry that points
        back to *target_version*).

        Returns:
            The newly created active version.
        """
        with self._lock:
            versions = self._load(tool_id)
            if not versions:
                raise FileNotFoundError(f"工具 {tool_id} 不存在")

            target: Optional[ToolVersion] = None
            for v in versions:
                if v.version == target_version:
                    target = v
                    break
            if target is None:
                raise ValueError(f"版本 {target_version} 不存在")

            # Mark current active versions
            for v in versions:
                if v.status == "active":
                    v.status = "rolled_back"

            new_ver = ToolVersion(
                tool_id=tool_id,
                version=_bump_minor(versions[-1].version),
                name=target.name,
                description=target.description,
                code=target.code,
                created_at=_now_iso(),
                created_by="system",
                parent_version=target_version,
                change_reason=f"回滚至版本 {target_version}",
            )
            versions.append(new_ver)
            self._save(tool_id, versions)
        return new_ver

    def deprecate(self, tool_id: str) -> None:
        """Deprecate all active versions of a tool."""
        with self._lock:
            versions = self._load(tool_id)
            if not versions:
                raise FileNotFoundError(f"工具 {tool_id} 不存在")
            for v in versions:
                if v.status == "active":
                    v.status = "deprecated"
            self._save(tool_id, versions)

    def search(self, query: str) -> List[ToolVersion]:
        """Search active tools by name or description (case-insensitive)."""
        q = query.lower()
        results: List[ToolVersion] = []
        with self._lock:
            for fname in os.listdir(self.storage_dir):
                if not fname.endswith(".json"):
                    continue
                tool_id = fname[: -len(".json")]
                for v in self._load(tool_id):
                    if v.status != "active":
                        continue
                    if q in v.name.lower() or q in v.description.lower():
                        results.append(v)
                        break
        return results

    def test_tool(self, tool_id: str, test_input: str) -> Dict:
        """Execute the active version of a tool in a sandboxed namespace.

        Returns:
            ``{'success': bool, 'output': Any, 'error': Optional[str],
              'execution_time': float}``
        """
        tv = self.get_active(tool_id)
        if tv is None:
            return {"success": False, "output": None, "error": f"工具 {tool_id} 无活跃版本", "execution_time": 0.0}

        # --- sandboxed exec namespace ---
        _BLOCKED_BUILTINS = {
            "exec", "eval", "compile", "__import__", "open",
            "input", "breakpoint", "exit", "quit",
        }
        _safe_builtins = {
            k: v for k, v in __builtins__.items()
            if k not in _BLOCKED_BUILTINS
        } if isinstance(__builtins__, dict) else {
            k: getattr(__builtins__, k)
            for k in dir(__builtins__)
            if not k.startswith("_") and k not in _BLOCKED_BUILTINS
        }
        namespace: Dict = {"__builtins__": _safe_builtins}

        # --- 超时保护 ---
        class _TimeoutError(Exception):
            pass

        def _timeout_handler(signum, frame):
            raise _TimeoutError("工具执行超时（5秒）")

        start = time.time()
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(5)  # 5秒超时
            try:
                exec(tv.code, namespace)  # noqa: S102
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            fn = namespace.get(tv.name)
            if fn is None:
                raise NameError(f"工具代码中未定义函数 '{tv.name}'")
            result = fn(test_input)
            elapsed = time.time() - start

            # Record success
            record = {"input": test_input, "output": repr(result), "success": True}
            with self._lock:
                versions = self._load(tool_id)
                for v in versions:
                    if v.version == tv.version:
                        v.test_results.append(record)
                        break
                self._save(tool_id, versions)

            return {"success": True, "output": result, "error": None, "execution_time": elapsed}
        except Exception as exc:
            elapsed = time.time() - start
            record = {"input": test_input, "output": None, "success": False, "error": str(exc)}
            with self._lock:
                versions = self._load(tool_id)
                for v in versions:
                    if v.version == tv.version:
                        v.test_results.append(record)
                        break
                self._save(tool_id, versions)
            return {"success": False, "output": None, "error": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}", "execution_time": elapsed}


# ---------------------------------------------------------------------------
# ToolEvolver — LLM-driven tool analysis & evolution
# ---------------------------------------------------------------------------

class ToolEvolver:
    """LLM-powered tool evolution engine.

    Parameters:
        registry: The :class:`ToolRegistry` to operate on.
        llm_fn:   Callable ``(system_prompt, user_prompt) -> str`` that wraps
                  an LLM chat completion.  Prompts and expected responses are
                  in Chinese (optimised for GLM-5.1).
    """

    def __init__(self, registry: ToolRegistry, llm_fn: Callable[[str, str], str]) -> None:
        self.registry = registry
        self.llm_fn = llm_fn

    # -- analysis ---------------------------------------------------------

    def analyze_failure(
        self,
        tool_id: str,
        task_desc: str,
        error_msg: str,
    ) -> Dict:
        """Ask the LLM why a tool failed.

        Returns:
            ``{'reason': str, 'suggestions': list[str]}``
        """
        tv = self.registry.get_active(tool_id)
        if tv is None:
            return {"reason": f"工具 {tool_id} 不存在", "suggestions": []}

        system_prompt = (
            "你是一个专业的Python工具分析专家。你的任务是分析工具失败的原因并给出改进建议。"
            "请用JSON格式回复，包含 'reason'（失败原因）和 'suggestions'（改进建议列表）两个键。"
        )
        user_prompt = (
            f"## 工具信息\n"
            f"- 名称: {tv.name}\n"
            f"- 描述: {tv.description}\n"
            f"- 当前版本: {tv.version}\n\n"
            f"## 工具代码\n```python\n{tv.code}\n```\n\n"
            f"## 任务描述\n{task_desc}\n\n"
            f"## 错误信息\n```\n{error_msg}\n```\n\n"
            f"请分析此工具失败的原因并给出具体的改进建议。"
        )

        raw = self.llm_fn(system_prompt, user_prompt)
        try:
            # Try to extract JSON from the response
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return {"reason": raw, "suggestions": []}

    # -- evolution --------------------------------------------------------

    def evolve_tool(
        self,
        tool_id: str,
        failure_analysis: Dict,
        task_desc: str,
    ) -> ToolVersion:
        """Let the LLM generate improved code and register a new version.

        Returns:
            The newly created :class:`ToolVersion`.
        """
        tv = self.registry.get_active(tool_id)
        if tv is None:
            raise FileNotFoundError(f"工具 {tool_id} 不存在")

        system_prompt = (
            "你是一个资深的Python开发者。你的任务是根据失败分析改进工具代码。"
            "请只输出改进后的完整Python代码，不要包含任何解释或markdown标记。"
            "代码必须定义一个名为 '{name}' 的函数。该函数接收一个字符串参数。"
        ).format(name=tv.name)

        suggestions = "\n".join(f"- {s}" for s in failure_analysis.get("suggestions", []))
        user_prompt = (
            f"## 当前工具代码\n```python\n{tv.code}\n```\n\n"
            f"## 任务描述\n{task_desc}\n\n"
            f"## 失败原因\n{failure_analysis.get('reason', '未知')}\n\n"
            f"## 改进建议\n{suggestions}\n\n"
            f"请输出改进后的完整Python代码（仅代码，不要markdown标记）。"
        )

        raw_code = self.llm_fn(system_prompt, user_prompt)
        # Strip markdown fences if the LLM wrapped the code
        cleaned = re.sub(r"^```(?:python)?\s*", "", raw_code)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)

        return self.registry.evolve(
            tool_id=tool_id,
            new_code=cleaned,
            reason=failure_analysis.get("reason", "LLM自动改进"),
            created_by="ToolEvolver",
        )

    # -- auto loop --------------------------------------------------------

    def auto_evolve(
        self,
        tool_id: str,
        task_desc: str,
        error_msg: str,
        max_attempts: int = 3,
    ) -> ToolVersion:
        """Full auto-evolution loop: analyse → evolve → test → retry.

        Iterates up to *max_attempts* times.  On each iteration:

        1. Analyse the failure.
        2. Evolve the tool (LLM generates new code).
        3. Test the new version with *task_desc* as input.

        If the test passes the loop stops early.  If all attempts are
        exhausted the **last** created version is returned regardless
        of test outcome.

        Returns:
            The latest :class:`ToolVersion` (hopefully working).
        """
        last_error = error_msg
        current_tv: Optional[ToolVersion] = None

        for attempt in range(1, max_attempts + 1):
            # 1. Analyse
            analysis = self.analyze_failure(tool_id, task_desc, last_error)

            # 2. Evolve
            current_tv = self.evolve_tool(tool_id, analysis, task_desc)

            # 3. Test
            result = self.registry.test_tool(tool_id, task_desc)
            if result["success"]:
                return current_tv

            last_error = result.get("error", "未知错误")

        # Return whatever we have after exhausting attempts
        if current_tv is None:
            raise RuntimeError(f"自动演化失败: 工具 {tool_id} 无法在 {max_attempts} 次尝试内完成演化")
        return current_tv


# ---------------------------------------------------------------------------
# TEAProtocol — coordinator that hooks into DAG execution
# ---------------------------------------------------------------------------

class TEAProtocol:
    """TEA Protocol coordinator.

    Hooks into a DAG execution lifecycle to provide the right tool for a
    task and trigger automatic evolution on failure.

    Parameters:
        registry:         The :class:`ToolRegistry`.
        evolver:          The :class:`ToolEvolver`.
        dag_executor_hook: Optional callable for notifying the wider DAG
                          executor about tool changes.  Signature:
                          ``(event: str, node, tool_version) -> None``.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        evolver: ToolEvolver,
        dag_executor_hook: Optional[Callable] = None,
    ) -> None:
        self.registry = registry
        self.evolver = evolver
        self.dag_executor_hook = dag_executor_hook

    # -- lifecycle hooks --------------------------------------------------

    def before_execute(self, node: str, tool_id: str) -> Optional[ToolVersion]:
        """Retrieve the active tool version before a node executes.

        Returns:
            The active :class:`ToolVersion`, or ``None`` if not found.
        """
        tv = self.registry.get_active(tool_id)
        if tv is not None and self.dag_executor_hook:
            self.dag_executor_hook("tool_ready", node, tv)
        return tv

    def on_failure(
        self,
        node: str,
        tool_id: str,
        error: str,
        task_desc: str = "",
        max_evolve_attempts: int = 3,
    ) -> Optional[ToolVersion]:
        """Trigger automatic evolution when a tool fails.

        Returns:
            The evolved (and hopefully working) :class:`ToolVersion`, or
            ``None`` if the tool could not be found.
        """
        tv = self.registry.get_active(tool_id)
        if tv is None:
            return None

        desc = task_desc or f"节点 {node} 执行失败"

        evolved = self.evolver.auto_evolve(
            tool_id=tool_id,
            task_desc=desc,
            error_msg=error,
            max_attempts=max_evolve_attempts,
        )

        if self.dag_executor_hook:
            self.dag_executor_hook("tool_evolved", node, evolved)

        return evolved

    # -- reporting --------------------------------------------------------

    def report(self) -> Dict:
        """Generate a summary of tool evolution history.

        Returns:
            ``{'total_tools': int, 'active_tools': int,
              'total_versions': int, 'evolution_log': list[dict]}``
        """
        all_tools = self.registry.list_tools()
        total_versions = 0
        evolution_log: List[Dict] = []

        for tv in all_tools:
            hist = self.registry.history(tv.tool_id)
            total_versions += len(hist)
            for v in hist:
                evolution_log.append({
                    "tool_id": v.tool_id,
                    "name": v.name,
                    "version": v.version,
                    "status": v.status,
                    "created_at": v.created_at,
                    "created_by": v.created_by,
                    "parent_version": v.parent_version,
                    "change_reason": v.change_reason,
                    "test_pass_count": sum(1 for t in v.test_results if t.get("success")),
                    "test_fail_count": sum(1 for t in v.test_results if not t.get("success")),
                })

        return {
            "total_tools": len(all_tools),
            "active_tools": sum(1 for t in all_tools if t.status == "active"),
            "total_versions": total_versions,
            "evolution_log": evolution_log,
        }
