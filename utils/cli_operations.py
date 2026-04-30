"""CLI operation logging and validation.

The log is append-only JSONL. It records human-operated CLI actions without
making any CLI a status writer or wiki writer.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from utils.atomic_io import atomic_append


DEFAULT_LOG_FILE = Path("logs/cli_operations.jsonl")
REQUIRED_FIELDS = {"ts", "cli", "actor", "action", "target_path", "outcome"}
PROTECTED_WRITE_PREFIXES = (
    "wiki/",
    "domains/game/wiki/",
    "domains/market/wiki/",
    "domains/personal/wiki/",
)
PROTECTED_JOB_PREFIX = "work/jobs/"
WRITE_ACTIONS = {"write", "edit", "delete", "move", "promote", "status_update"}
APPROVED_WIKI_WRITERS = {"promote.py"}
APPROVED_STATUS_WRITERS = {"wiki_daemon.py", "approve.py"}


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_target_path(target_path: str | Path, root: Path | None = None) -> str:
    root = (root or Path.cwd()).resolve()
    path = Path(target_path)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def build_cli_operation(
    *,
    cli: str,
    action: str,
    target_path: str | Path,
    outcome: str,
    actor: str | None = None,
    job_id: str | None = None,
    detail: str = "",
    root: Path | None = None,
) -> dict[str, Any]:
    return {
        "ts": utc_now(),
        "cli": cli,
        "actor": actor or os.environ.get("USERNAME") or os.environ.get("USER") or "operator",
        "action": action,
        "target_path": normalize_target_path(target_path, root),
        "outcome": outcome,
        "job_id": job_id or "",
        "detail": detail,
    }


def log_cli_operation(operation: dict[str, Any], log_path: Path = DEFAULT_LOG_FILE) -> None:
    errors = validate_cli_operation(operation)
    if errors:
        raise ValueError("; ".join(errors))
    atomic_append(log_path, json.dumps(operation, ensure_ascii=False))


def validate_cli_operation(operation: dict[str, Any]) -> list[str]:
    errors = []
    missing = sorted(REQUIRED_FIELDS - set(operation))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    action = str(operation.get("action", ""))
    cli = str(operation.get("cli", ""))
    target_path = str(operation.get("target_path", "")).replace("\\", "/").lstrip("./")

    if action in WRITE_ACTIONS:
        if target_path.startswith(PROTECTED_WRITE_PREFIXES) and cli not in APPROVED_WIKI_WRITERS:
            errors.append("wiki writes must go through promote.py")
        if target_path.startswith(PROTECTED_JOB_PREFIX) and action == "status_update" and cli not in APPROVED_STATUS_WRITERS:
            errors.append("JOB status updates must go through wiki_daemon.py or approve.py")
        if target_path in {".env", ".env.local"} or target_path.startswith(".env."):
            errors.append("CLI operation log must not record writes to secret env files")

    return errors


def load_cli_operations(log_path: Path) -> list[dict[str, Any]]:
    operations = []
    if not log_path.exists():
        return operations
    for line_no, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            operations.append({"_line": line_no, "_error": str(exc)})
            continue
        entry["_line"] = line_no
        operations.append(entry)
    return operations
