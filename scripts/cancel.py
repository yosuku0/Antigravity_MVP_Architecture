#!/usr/bin/env python3
"""
cancel.py — Cancel a running/stuck job

Actions:
  1. Remove lock file
  2. Purge staged artifacts
  3. Update daemon state to 'cancelled'
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LOCK_DIR = Path("work/locks")
STAGE_DIR = Path("work/staged")
STATE_FILE = Path("work/daemon_state.json")
LOG_FILE = Path("work/daemon.jsonl")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"jobs": {}}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"jobs": {}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cancel a job")
    parser.add_argument("job_id", help="Job ID to cancel")
    parser.add_argument("--purge", action="store_true", help="Also delete staged artifacts")
    args = parser.parse_args()

    # Remove lock
    lock_path = LOCK_DIR / f"{args.job_id}.lock"
    if lock_path.exists():
        lock_path.unlink()
        print(f"[OK] Removed lock: {lock_path}")
    else:
        print(f"[INFO] No lock found for {args.job_id}")

    # Update state
    state = load_state()
    if args.job_id in state.get("jobs", {}):
        state["jobs"][args.job_id]["status"] = "cancelled"
        save_state(state)
        print(f"[OK] State updated to 'cancelled'")
    else:
        print(f"[WARN] Job {args.job_id} not found in state")

    # Purge staged artifacts
    if args.purge:
        for artifact in STAGE_DIR.glob(f"{args.job_id}*"):
            artifact.unlink()
            print(f"[OK] Purged: {artifact}")

    # Log
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "cancel",
        "job_id": args.job_id,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
