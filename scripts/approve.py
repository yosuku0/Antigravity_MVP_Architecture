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

LOG_FILE = Path("work/daemon.jsonl")


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
