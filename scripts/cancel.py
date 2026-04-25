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
import yaml
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LOCK_DIR = Path("work/locks")
STAGE_DIR = Path("work/staged")
STATE_FILE = Path("work/daemon_state.json")
LOG_FILE = Path("work/daemon.jsonl")


def load_state(state_file: Path = STATE_FILE) -> dict:
    if not state_file.exists():
        return {"jobs": {}}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"jobs": {}}


def save_state(state: dict, state_file: Path = STATE_FILE) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def cancel_job(job_path: Path, repo_root: Path | None = None) -> None:
    """Cancel a job: remove lock, purge staging, update status to cancelled."""
    root = repo_root if repo_root else Path(".")
    
    # Read frontmatter to get job_id
    text = job_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) >= 3:
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            fm = {}
        if fm is None:
            fm = {}
        body = parts[2]
    else:
        fm = {}
        body = text
    
    job_id = fm.get("job_id", job_path.stem)
    
    # Remove lock
    lock_path = root / "work" / "locks" / f"{job_id}.lock"
    if lock_path.exists():
        lock_path.unlink()
    
    # Remove staging
    staging_dir = root / "work" / "artifacts" / "staging" / job_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    
    # Update frontmatter status
    fm["status"] = "cancelled"
    yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    content = f"---\n{yaml_str}---\n{body}"
    job_path.write_text(content, encoding="utf-8")
    
    # Update daemon state
    state_file = root / "work" / "daemon_state.json"
    if state_file.exists():
        try:
            state = load_state(state_file)
            if job_id in state.get("jobs", {}):
                state["jobs"][job_id]["status"] = "cancelled"
                save_state(state, state_file)
        except Exception:
            pass

    # Log
    log_file = root / "work" / "daemon.jsonl"
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "cancel",
        "job_id": job_id,
    }
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cancel a job")
    parser.add_argument("job_id", help="Job ID to cancel")
    parser.add_argument("--purge", action="store_true", help="Also delete staged artifacts (deprecated in cancel_job, handled by default)")
    args = parser.parse_args()

    # Find job file
    job_path = Path("work/jobs") / f"{args.job_id}.md"
    if not job_path.exists():
        # Try finding by looking into the directory if the ID doesn't match the filename perfectly
        jobs = list(Path("work/jobs").glob("*.md"))
        for j in jobs:
            if args.job_id in j.name:
                job_path = j
                break
    
    if not job_path.exists():
        print(f"[ERROR] Job file not found for {args.job_id}")
        return 1

    cancel_job(job_path)
    print(f"[OK] Job {args.job_id} cancelled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
