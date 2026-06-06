"""Evidence redaction helpers for compact public artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable
import json
import os
import re

REPO_ROOT_LABEL = "$REPO_ROOT"
HOME_LABEL = "$HOME"
SECRET_LABEL = "$REDACTED_VALUE"  # nosec B105
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{20,}",
    r"BEGIN [A-Z ]*PRIVATE KEY",
    r"(?i)(password|secret|token)\\s*[:=]\\s*['\"][^'\"]{8,}",
]


def repo_root(start: str = ".") -> Path:
    """Return the git repository root for path sanitization."""
    path = Path(start).resolve()
    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return candidate
    return path


def sanitize_text(value: str, root: str = ".") -> str:
    """Replace local absolute paths and obvious secret-looking values."""
    repo = str(repo_root(root))
    home = str(Path.home())
    text = str(value)
    replacements = [
        (repo, REPO_ROOT_LABEL),
        (home, HOME_LABEL),
    ]
    for source, target in replacements:
        if source:
            text = text.replace(source, target)
    for pattern in SECRET_PATTERNS:
        text = re.sub(pattern, SECRET_LABEL, text)
    return text


def sanitize_value(value: Any, root: str = ".") -> Any:
    """Recursively sanitize evidence values while preserving JSON shape."""
    if isinstance(value, str):
        return sanitize_text(value, root=root)
    if isinstance(value, list):
        return [sanitize_value(item, root=root) for item in value]
    if isinstance(value, tuple):
        return [sanitize_value(item, root=root) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize_value(item, root=root) for key, item in value.items()}
    return value


def sanitize_payload(payload: Dict[str, Any], root: str = ".") -> Dict[str, Any]:
    """Return a public-evidence payload with stable sanitization metadata."""
    sanitized = sanitize_value(dict(payload), root=root)
    sanitized["sanitized"] = True
    sanitized["repo_root_label"] = REPO_ROOT_LABEL
    return sanitized


def sanitize_file(path: str, root: str = ".") -> None:
    """Sanitize one committed evidence file in place."""
    file_path = Path(path)
    if not file_path.exists():
        return
    body = file_path.read_text(encoding="utf-8")
    file_path.write_text(sanitize_text(body, root=root), encoding="utf-8")


def sanitize_files(paths: Iterable[str], root: str = ".") -> None:
    for path in paths:
        sanitize_file(path, root=root)


def sensitive_hits(path: str) -> list[str]:
    """Return lines that still contain local-path or credential-looking markers."""
    patterns = [
        re.escape(str(Path.home())),
        r"/Users/[^\\s\"'<]+",
        *SECRET_PATTERNS,
    ]
    hits: list[str] = []
    file_path = Path(path)
    if not file_path.exists():
        return hits
    for index, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if any(re.search(pattern, line) for pattern in patterns):
            hits.append(f"{file_path}:{index}:{line[:240]}")
    return hits


def dumps_public_json(payload: Dict[str, Any], root: str = ".") -> str:
    return json.dumps(sanitize_payload(payload, root=root), ensure_ascii=False, indent=2)


def is_writable_dir(path: str) -> bool:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return os.access(str(target), os.W_OK)
