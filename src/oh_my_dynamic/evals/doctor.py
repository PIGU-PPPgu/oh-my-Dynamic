"""Environment checks for oh-my-Dynamic adoption and release gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

from oh_my_dynamic.evals.evidence_sanitizer import is_writable_dir, sensitive_hits


@dataclass
class DoctorCheck:
    name: str
    status: str
    message: str
    metadata: Dict[str, Any]


def _run(
    cmd: List[str],
    cwd: str = ".",
    *,
    input_text: Optional[str] = None,
    timeout_s: Optional[int] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def _check_codex_cli(codex_bin: str) -> DoctorCheck:
    path = shutil.which(codex_bin)
    if not path:
        return DoctorCheck("codex_cli", "warn", f"{codex_bin!r} was not found on PATH", {})
    result = _run([codex_bin, "--version"])
    status = "pass" if result.returncode == 0 else "warn"
    version = (result.stdout or result.stderr).strip().splitlines()[:1]
    return DoctorCheck("codex_cli", status, "Codex CLI is available", {"path": path, "version": version[0] if version else ""})


def _check_codex_exec_smoke(codex_bin: str, cwd: str, timeout_s: int) -> DoctorCheck:
    path = shutil.which(codex_bin)
    if not path:
        return DoctorCheck(
            "codex_exec_smoke",
            "fail",
            f"{codex_bin!r} was not found on PATH; real Codex CLI workers cannot run",
            {},
        )
    output_path = Path(cwd).resolve() / ".orchestry" / "doctor" / "codex_exec_smoke.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = "Return exactly this text and nothing else: oh-my-dynamic doctor smoke"
    cmd = [
        codex_bin,
        "exec",
        "--cd",
        str(Path(cwd).resolve()),
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "--output-last-message",
        str(output_path),
        "-",
    ]
    try:
        result = _run(cmd, cwd=cwd, input_text=prompt, timeout_s=timeout_s)
    except subprocess.TimeoutExpired:
        return DoctorCheck(
            "codex_exec_smoke",
            "fail",
            f"codex exec smoke timed out after {timeout_s}s",
            {"output_path": str(output_path)},
        )
    preview = ""
    if output_path.exists():
        preview = output_path.read_text(encoding="utf-8", errors="replace").strip()[:160]
    if result.returncode != 0:
        return DoctorCheck(
            "codex_exec_smoke",
            "fail",
            "codex exec smoke failed; Codex CLI may be logged out or blocked by sandbox/config",
            {
                "returncode": result.returncode,
                "stdout_preview": (result.stdout or "")[:160],
                "stderr_preview": (result.stderr or "")[:160],
                "output_path": str(output_path),
            },
        )
    return DoctorCheck(
        "codex_exec_smoke",
        "pass",
        "codex exec smoke completed",
        {"output_path": str(output_path), "preview": preview},
    )


def _check_git_repo(cwd: str) -> DoctorCheck:
    result = _run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if result.returncode != 0:
        return DoctorCheck("git_repo", "fail", "Current directory is not inside a git repository", {"cwd": str(Path(cwd).resolve())})
    root = result.stdout.strip()
    dirty = _run(["git", "status", "--short"], cwd=cwd).stdout.strip()
    return DoctorCheck("git_repo", "pass", "Git repository detected", {"root": root, "dirty": bool(dirty)})


def _check_marketplace(path: str) -> DoctorCheck:
    marketplace = Path(path).expanduser()
    if not marketplace.exists():
        return DoctorCheck("marketplace_json", "warn", "Marketplace JSON does not exist yet", {"path": str(marketplace)})
    try:
        payload = json.loads(marketplace.read_text(encoding="utf-8"))
    except Exception as exc:
        return DoctorCheck("marketplace_json", "fail", f"Marketplace JSON could not be parsed: {exc}", {"path": str(marketplace)})
    plugins = payload.get("plugins", []) if isinstance(payload, dict) else []
    plugin = next((item for item in plugins if item.get("name") == "oh-my-dynamic"), None)
    has_plugin = plugin is not None
    source_path = ((plugin or {}).get("source") or {}).get("path", "")
    return DoctorCheck(
        "marketplace_json",
        "pass" if has_plugin else "warn",
        "Marketplace JSON is parseable" + (" and references oh-my-dynamic" if has_plugin else ""),
        {"path": str(marketplace), "has_oh_my_dynamic": has_plugin, "source_path": source_path},
    )


def _check_skill_link(path: str) -> DoctorCheck:
    skill = Path(path).expanduser()
    if not skill.exists():
        return DoctorCheck("skill_link", "warn", "Installed skill link was not found", {"path": str(skill)})
    return DoctorCheck(
        "skill_link",
        "pass",
        "Installed skill path exists",
        {
            "path": str(skill),
            "is_symlink": skill.is_symlink(),
            "target": os.readlink(skill) if skill.is_symlink() else "",
        },
    )


def _check_writable_orchestry(path: str) -> DoctorCheck:
    try:
        writable = is_writable_dir(path)
    except Exception as exc:
        return DoctorCheck("orchestry_writable", "fail", f"Workspace evidence directory is not writable: {exc}", {"path": path})
    return DoctorCheck("orchestry_writable", "pass" if writable else "fail", "Evidence workspace is writable", {"path": path})


def _check_gateway_auth(host: str, token: str) -> DoctorCheck:
    loopback = host in {"127.0.0.1", "localhost", "::1"}
    if loopback:
        return DoctorCheck("gateway_auth", "pass", "Gateway host is loopback", {"host": host, "token_configured": bool(token)})
    if token:
        return DoctorCheck("gateway_auth", "pass", "Gateway token configured for non-loopback host", {"host": host})
    return DoctorCheck("gateway_auth", "fail", "Non-loopback gateway host requires an auth token", {"host": host})


def _check_evidence_redaction(pattern: str) -> DoctorCheck:
    paths = sorted(Path(path) for path in glob.glob(pattern))
    hits: List[str] = []
    for path in paths:
        if path.is_file():
            hits.extend(sensitive_hits(str(path))[:5])
    if hits:
        return DoctorCheck("evidence_redaction", "fail", "Committed evidence still contains sensitive markers", {"hits": hits[:20]})
    return DoctorCheck("evidence_redaction", "pass", "Committed evidence passed local path/API-key marker scan", {"files": len(paths)})


def run_doctor(args: argparse.Namespace) -> Dict[str, Any]:
    strict_real_codex = bool(getattr(args, "strict_real_codex", False))
    checks = [
        _check_codex_cli(args.codex_bin),
        _check_git_repo(args.cd),
        _check_marketplace(args.marketplace_json),
        _check_skill_link(args.skill_path),
        _check_writable_orchestry(args.orchestry_dir),
        _check_gateway_auth(args.gateway_host, args.gateway_token or os.environ.get("OH_MY_DYNAMIC_GATEWAY_TOKEN", "")),
        _check_evidence_redaction(args.evidence_glob),
    ]
    if strict_real_codex:
        checks.append(_check_codex_exec_smoke(args.codex_bin, args.cd, int(getattr(args, "codex_exec_timeout_s", 60))))
    ready_for_real_codex_cli = strict_real_codex and all(
        check.status == "pass"
        for check in checks
        if check.name in {"codex_cli", "git_repo", "orchestry_writable", "codex_exec_smoke"}
    )
    if strict_real_codex and not any(check.name == "codex_exec_smoke" for check in checks):
        ready_for_real_codex_cli = False
    if any(check.status == "fail" for check in checks):
        status = "fail"
    elif any(check.status == "warn" for check in checks):
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "ready_for_real_codex_cli": ready_for_real_codex_cli,
        "strict_real_codex": strict_real_codex,
        "checks": [asdict(check) for check in checks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check oh-my-Dynamic local installation and release-readiness.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--strict-real-codex", action="store_true", help="Run a real `codex exec` smoke and fail if real workers are not ready.")
    parser.add_argument("--codex-exec-timeout-s", type=int, default=60)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--cd", default=".")
    parser.add_argument("--marketplace-json", default="~/.agents/plugins/marketplace.json")
    parser.add_argument("--skill-path", default="~/.agents/skills/oh-my-dynamic")
    parser.add_argument("--orchestry-dir", default=".orchestry")
    parser.add_argument("--gateway-host", default="127.0.0.1")
    parser.add_argument("--gateway-token", default="")
    parser.add_argument("--evidence-glob", default="docs/evidence/*")
    args = parser.parse_args()
    result = run_doctor(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"oh-my-Dynamic doctor: {result['status']}")
        for check in result["checks"]:
            print(f"- {check['status'].upper():4} {check['name']}: {check['message']}")
    raise SystemExit(1 if result["status"] == "fail" else 0)


if __name__ == "__main__":
    main()
