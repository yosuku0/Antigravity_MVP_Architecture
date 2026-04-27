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

from utils.atomic_io import atomic_write, read_frontmatter, write_frontmatter

LOG_FILE = Path("work/daemon.jsonl")


# ── State Machine Configuration ───────────────────────────────────────

ALLOWED_APPROVAL_TRANSITIONS = {
    2: {
        "from": {"audit_passed"},
        "to": "approved_gate_2",
        "by_field": "approved_gate_2_by",
        "at_field": "approved_gate_2_at",
    },
    3: {
        "from": {"promotion_pending"},
        "to": "approved_gate_3",
        "by_field": "approved_gate_3_by",
        "at_field": "approved_gate_3_at",
    },
}

# ── Business Logic ───────────────────────────────────────────────────

def approve_gate_1(job_path: Path, approver: str, reject: bool = False, reason: str = "") -> None:
    """Gate 1 is currently flexible but records status."""
    fm, body = read_frontmatter(job_path)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    if reject:
        fm["status"] = "gate_1_rejected"
        fm["gate_1_rejected_by"] = approver
        body = _append_feedback(body, 1, reason)
    else:
        fm["status"] = "approved_gate_1"
        fm["approved_by"] = approver
        fm["approved_at"] = now
        
    write_frontmatter(job_path, fm, body)
    log_approval(fm.get("job_id", job_path.stem), 1, not reject, reason)


def process_approval(job_path: Path, gate: int, approver: str, reject: bool = False, reason: str = "") -> bool:
    """Consolidated state-aware approval logic for Gate 2 and 3."""
    if gate == 1:
        approve_gate_1(job_path, approver, reject, reason)
        return True

    # Gate 3 Reject is not supported in MVP
    if reject and gate == 3:
        print("[ERROR] Gate 3 reject is not supported in this MVP.")
        return False

    fm, body = read_frontmatter(job_path)
    current_status = fm.get("status", "created")
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    config = ALLOWED_APPROVAL_TRANSITIONS.get(gate)
    if not config:
        print(f"[ERROR] Unsupported gate: {gate}")
        return False

    # STRICT STATE CHECK
    if current_status not in config["from"]:
        print(f"[ERROR] Gate {gate} DENIED.")
        print(f"Current Status: '{current_status}'")
        print(f"Required Status: one of {config['from']}")
        return False

    if reject:
        if gate == 2:
            fm["status"] = "gate_2_rejected"
            fm["rejected_gate"] = 2
            fm["rejected_by"] = approver
            fm["rejected_at"] = now
            fm["reject_reason"] = reason
            body = _append_feedback(body, 2, reason)
        else:
            # Should not reach here if gate==3 check is above, but for safety:
            print(f"[ERROR] Reject not supported for gate {gate}")
            return False
    else:
        # APPROVE
        fm["status"] = config["to"]
        fm[config["by_field"]] = approver
        fm[config["at_field"]] = now

    write_frontmatter(job_path, fm, body)
    log_approval(fm.get("job_id", job_path.stem), gate, not reject, reason)
    return True


def _append_feedback(body: str, gate: int, reason: str) -> str:
    """Append rejection feedback to the markdown body."""
    if not reason:
        return body
    header = f"\n\n## Reject Feedback (Gate {gate})\n"
    return body + header + reason + "\n"


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
    parser.add_argument("--approver", default=None, help="Approver name")
    args = parser.parse_args()

    job_path = Path(args.job)
    if not job_path.exists():
        job_path = Path("work/jobs") / f"{args.job}.md"
    if not job_path.exists():
        print(f"[ERROR] Job not found: {args.job}")
        return 1

    import os
    approver = args.approver or os.environ.get("USER") or os.environ.get("USERNAME") or "operator"

    success = process_approval(job_path, args.gate, approver, args.reject, args.reason)
    
    if not success:
        return 1

    if args.reject:
        print(f"Gate {args.gate}: REJECTED")
    else:
        print(f"Gate {args.gate}: APPROVED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
