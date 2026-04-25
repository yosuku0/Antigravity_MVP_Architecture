#!/usr/bin/env python3
"""
approve.py — HITL Gate 1/2/3 CLI approval

Usage:
    python scripts/approve.py --gate 1 --job JOB-001    # Approve Gate 1
    python scripts/approve.py --gate 2 --job JOB-001    # Approve Gate 2
    python scripts/approve.py --reject --job JOB-001    # Reject
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from utils.atomic_io import atomic_write

LOG_FILE = Path("work/daemon.jsonl")
def _read_frontmatter(job_path: Path) -> tuple[dict, str]:
    text = job_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) >= 3:
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            fm = {}
        # yaml.safe_load は空文字や不正入力で None を返す可能性がある
        if fm is None:
            fm = {}
        body = parts[2]
        return fm, body
    return {}, text


def _write_frontmatter(job_path: Path, fm: dict, body: str) -> None:
    # default_flow_style=False でブロック形式（可読性）を維持
    yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    if body.startswith('\n'):
        content = f"---\n{yaml_str}---{body}"
    else:
        content = f"---\n{yaml_str}---\n{body}"
    atomic_write(job_path, content)


def approve_gate_1(job_path: Path, approver: str) -> None:
    fm, body = _read_frontmatter(job_path)
    fm["status"] = "approved_gate_1"
    fm["approved_by"] = approver
    _write_frontmatter(job_path, fm, body)
    log_approval(fm.get("job_id", job_path.stem), 1, True)


def approve_gate_2(job_path: Path, approver: str, reject: bool = False) -> None:
    fm, body = _read_frontmatter(job_path)
    if reject:
        fm["status"] = "gate_2_rejected"
        fm["gate_2_rejected_by"] = approver
    else:
        fm["status"] = "staged"
        fm["approved_gate_2_by"] = approver
    _write_frontmatter(job_path, fm, body)
    log_approval(fm.get("job_id", job_path.stem), 2, not reject)


def approve_gate_3(job_path: Path, approver: str) -> None:
    fm, body = _read_frontmatter(job_path)
    fm["status"] = "promoted"
    fm["approved_gate_3_by"] = approver
    _write_frontmatter(job_path, fm, body)
    log_approval(fm.get("job_id", job_path.stem), 3, True)


def log_approval(job_id: str, gate: int, approved: bool, reason: str = "") -> None:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "hitl_gate",
        "job_id": job_id,
        "gate": gate,
        "approved": approved,
        "reason": reason,
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="HITL Gate approval")
    parser.add_argument("--job", required=True, help="Job ID")
    parser.add_argument("--gate", type=int, choices=[1, 2, 3], default=1, help="Gate number")
    parser.add_argument("--reject", action="store_true", help="Reject instead of approve")
    parser.add_argument("--reason", default="", help="Rejection reason")
    args = parser.parse_args()

    if args.reject:
        print(f"\n{'='*50}")
        print(f"  Gate {args.gate}: REJECTED")
        print(f"  Job: {args.job}")
        if args.reason:
            print(f"  Reason: {args.reason}")
        print(f"{'='*50}\n")
        log_approval(args.job, args.gate, False, args.reason)
        return 2

    print(f"\n{'='*50}")
    print(f"  Gate {args.gate}: APPROVED")
    print(f"  Job: {args.job}")
    print(f"{'='*50}\n")
    log_approval(args.job, args.gate, True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
