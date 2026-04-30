#!/usr/bin/env python3
"""
scope_guard.py — Forbidden import detection

Prevents unauthorized dependencies from entering the codebase.
Slack dependencies are allowed only in ingress adapters and the Gate 2 Slack HITL daemon adapter.
Subprocess is restricted to explicitly approved infrastructure wrappers, dispatchers, scripts, and tests.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.cli_operations import load_cli_operations, validate_cli_operation

# Module → reason
FORBIDDEN = {
    "requests": "Use urllib from stdlib",
    "httpx": "Use urllib from stdlib",
}

# Module → allowed paths
ALLOWED_PATHS = {
    # Slack Gate 2 HITL adapter
    "slack_bolt": ["apps/ingress/", "apps/daemon/slack_adapter.py"],
    "slack_sdk": ["apps/ingress/", "apps/daemon/slack_adapter.py"],
    # Subprocess allowed only in low-level utils or specific dispatchers
    "subprocess": [
        "utils/safe_subprocess.py",
        "utils/docker_executor.py",  # Docker sandbox execution wrapper
        "apps/daemon/wiki_daemon.py", # Controlled promotion subprocess dispatch
        "scripts/",
        "tests/",
    ],
}

IMPORT_RE = re.compile(r"^(?:import\s+(\S+)|from\s+(\S+)\s+import)", re.MULTILINE)


def scan_file(path: Path, root: Path) -> list[dict]:
    """Scan a single file for forbidden imports."""
    findings = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings

    rel = path.relative_to(root).as_posix()

    for match in IMPORT_RE.finditer(content):
        module = match.group(1) or match.group(2)
        base = module.split(".")[0]

        # Check forbidden
        if base in FORBIDDEN:
            findings.append({
                "file": rel,
                "line": content[:match.start()].count("\n") + 1,
                "module": base,
                "reason": FORBIDDEN[base],
                "severity": "ERROR",
            })

        # Check restricted paths
        if base in ALLOWED_PATHS:
            if not any(a in rel for a in ALLOWED_PATHS[base]):
                findings.append({
                    "file": rel,
                    "line": content[:match.start()].count("\n") + 1,
                    "module": base,
                    "reason": f"Allowed only in: {ALLOWED_PATHS[base]}",
                    "severity": "ERROR",
                })

    return findings


def scan_cli_operation_logs(root: Path) -> list[dict]:
    """Validate CLI operation logs and protected write boundaries."""
    findings = []
    for rel in ("logs/cli_operations.jsonl", "work/logs/cli_operations.jsonl"):
        log_path = root / rel
        for entry in load_cli_operations(log_path):
            if "_error" in entry:
                findings.append({
                    "file": rel,
                    "line": entry.get("_line", 0),
                    "module": "cli_operations",
                    "reason": f"Invalid JSONL: {entry['_error']}",
                    "severity": "ERROR",
                })
                continue
            for error in validate_cli_operation(entry):
                findings.append({
                    "file": rel,
                    "line": entry.get("_line", 0),
                    "module": "cli_operations",
                    "reason": error,
                    "severity": "ERROR",
                })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scope guard")
    parser.add_argument("root", nargs="?", default=".", help="Project root")
    args = parser.parse_args()

    root = Path(args.root)
    all_findings = []

    for path in root.rglob("*.py"):
        rel_posix = path.relative_to(root).as_posix()
        # Skip vendored code, memory artifacts, execution work dir, and local venvs
        skip_dirs = ["vendor/", "memory/", "work/", "venv/", ".venv/"]
        if any(sd in rel_posix for sd in skip_dirs):
            continue
        all_findings.extend(scan_file(path, root))

    all_findings.extend(scan_cli_operation_logs(root))

    if all_findings:
        print(f"\nScope violations found: {len(all_findings)}")
        for f in all_findings:
            print(f"  {f['file']}:{f['line']} - {f['module']} ({f['reason']})")
        return 1

    print("Scope guard passed - no forbidden imports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
