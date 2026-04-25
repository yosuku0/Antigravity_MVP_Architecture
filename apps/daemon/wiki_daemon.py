"""
wiki_daemon.py — File watchdog daemon with atomic locking

Responsibilities:
  1. Watch work/jobs/ for new .md JOB files
  2. Acquire atomic lock (O_CREAT | O_EXCL) per job
  3. Rebuild daemon_state.json from ground truth on startup
  4. Stale-lock reclaim (>10 min old, dead PID)
  5. Execute jobs via graph.py and log results
"""

from __future__ import annotations

import errno
import json
import os
import sys
import time
from pathlib import Path

from utils.atomic_io import atomic_write, atomic_append

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


LOCK_DIR = Path("work/locks")
JOBS_DIR = Path("work/jobs")
STAGE_DIR = Path("work/staged")
STATE_FILE = Path("work/daemon_state.json")
LOG_FILE = Path("work/daemon.jsonl")
STALE_MINUTES = 10


def rebuild_state() -> dict:
    """Rebuild daemon state from filesystem ground truth."""
    state = {
        "last_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "jobs": {},
    }
    if not JOBS_DIR.exists():
        return state

    for path in sorted(JOBS_DIR.glob("*.md")):
        job_id = path.stem
        state["jobs"][job_id] = {
            "status": "queued",
            "path": str(path),
            "created": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)
            ),
        }
    return state


def load_state() -> dict:
    """Load or rebuild daemon state."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Validate: check all referenced jobs still exist
            valid_jobs = {
                k: v for k, v in state.get("jobs", {}).items()
                if Path(v.get("path", "")).exists()
            }
            if len(valid_jobs) != len(state.get("jobs", {})):
                state["jobs"] = valid_jobs
                save_state(state)
            return state
        except (json.JSONDecodeError, KeyError):
            pass
    return rebuild_state()


def save_state(state: dict) -> None:
    """Atomically save daemon state."""
    atomic_write(STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False))


def try_lock(job_id: str) -> bool:
    """Try to acquire atomic lock for a job.

    Uses O_CREAT | O_EXCL for atomicity.
    Writes PID and timestamp into lock file.
    """
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_DIR / f"{job_id}.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            f.write(f"{os.getpid()}\n{time.time()}\n")
        return True
    except OSError as e:
        if e.errno == errno.EEXIST:
            return False
        raise


def release_lock(job_id: str) -> None:
    """Release lock for a job."""
    lock_path = LOCK_DIR / f"{job_id}.lock"
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def is_lock_stale(job_id: str) -> bool:
    """Check if a lock is stale (>10 min old or PID dead)."""
    lock_path = LOCK_DIR / f"{job_id}.lock"
    if not lock_path.exists():
        return False
    try:
        with open(lock_path, "r") as f:
            lines = f.read().strip().split("\n")
        if len(lines) >= 2:
            pid = int(lines[0])
            timestamp = float(lines[1])
            age_min = (time.time() - timestamp) / 60
            # Check PID liveness
            try:
                os.kill(pid, 0)
                pid_alive = True
            except OSError:
                pid_alive = False
            return age_min > STALE_MINUTES or not pid_alive
    except (ValueError, OSError):
        pass
    return False


def reclaim_stale_lock(job_id: str) -> bool:
    """Remove a stale lock and acquire a new one."""
    lock_path = LOCK_DIR / f"{job_id}.lock"
    try:
        lock_path.unlink()
        return try_lock(job_id)
    except OSError:
        return False


def log_event(event_type: str, job_id: str, detail: str = "") -> None:
    """Append event to daemon JSONL log."""
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": event_type,
        "job_id": job_id,
        "detail": detail,
    }
    atomic_append(LOG_FILE, json.dumps(entry, ensure_ascii=False))


def execute_job(job_id: str, job_path: str) -> dict:
    """Execute a job through graph.py."""
    try:
        from apps.runtime.graph import run_job
        result = run_job(job_path, job_id)
        return result
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def process_jobs() -> int:
    """Process all queued jobs. Returns number processed."""
    state = load_state()
    count = 0

    for job_id, job_info in state.get("jobs", {}).items():
        if job_info.get("status") in ("done", "failed"):
            continue

        # Try to acquire lock
        if not try_lock(job_id):
            if is_lock_stale(job_id):
                if not reclaim_stale_lock(job_id):
                    continue
            else:
                continue

        try:
            log_event("start", job_id)
            state["jobs"][job_id]["status"] = "running"
            save_state(state)

            result = execute_job(job_id, job_info["path"])

            state["jobs"][job_id]["status"] = result.get("status", "unknown")
            state["jobs"][job_id]["result"] = result
            save_state(state)

            detail = result.get("audit_result", "") or result.get("error", "")
            log_event("complete", job_id, detail)
            count += 1

        except Exception as e:
            state["jobs"][job_id]["status"] = "failed"
            state["jobs"][job_id]["error"] = str(e)
            save_state(state)
            log_event("error", job_id, str(e))

        finally:
            release_lock(job_id)

    return count


def main() -> None:
    """Run daemon for one pass (for cron/systemd) or continuously."""
    import argparse
    parser = argparse.ArgumentParser(description="Wiki Daemon")
    parser.add_argument(
        "--once", action="store_true", help="Process one batch and exit"
    )
    parser.add_argument(
        "--interval", type=int, default=30, help="Polling interval (seconds)"
    )
    args = parser.parse_args()

    # Ensure directories exist
    for d in (JOBS_DIR, STAGE_DIR, LOCK_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # Rebuild state on startup
    state = rebuild_state()
    save_state(state)
    log_event("startup", "daemon", f"{len(state['jobs'])} jobs queued")

    if args.once:
        processed = process_jobs()
        log_event("shutdown", "daemon", f"Processed {processed} jobs")
        return

    # Continuous mode
    print(f"Daemon started — watching {JOBS_DIR} (interval: {args.interval}s)")
    try:
        while True:
            processed = process_jobs()
            if processed > 0:
                print(f"  Processed {processed} jobs")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log_event("shutdown", "daemon", "SIGINT received")
        print("\nDaemon stopped")


if __name__ == "__main__":
    main()
