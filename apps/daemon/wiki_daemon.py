"""
wiki_daemon.py — File watchdog daemon with atomic locking

Responsibilities:
  1. Watch work/jobs/ for new .md JOB files
  2. Acquire atomic lock (O_CREAT | O_EXCL) per job
  3. Rebuild daemon_state.json from ground truth on startup
  4. Stale-lock reclaim (>10 min old, dead PID)
  5. Execute jobs via graph.py and log results
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path BEFORE local imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import errno
import yaml
import logging
from dotenv import load_dotenv
from utils.atomic_io import atomic_write, atomic_append
from utils.logging_config import get_logger

# Load environment variables
load_dotenv()

logger = get_logger("daemon")


def read_job_frontmatter(job_path: Path) -> dict:
    """Read YAML frontmatter from a JOB file."""
    try:
        text = job_path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return yaml.safe_load(parts[1]) or {}
        return {}
    except Exception as e:
        logger.warning(f"Failed to read frontmatter from {job_path}: {e}")
        return {}


LOCK_DIR = Path("work/locks")
JOBS_DIR = Path("work/jobs")
STAGE_DIR = Path("work/staged")
STATE_FILE = Path("work/daemon_state.json")
LOG_FILE = Path("work/daemon.jsonl")
STALE_MINUTES = 10
TERMINAL_STATUSES = {"done", "failed", "audit_failed", "promoted", "cancelled"}


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
        fm = read_job_frontmatter(path)
        state["jobs"][job_id] = {
            "status": fm.get("status", "created"),
            "path": str(path),
            "created": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)
            ),
        }
    return state


def reconcile_state(state: dict) -> dict:
    """Merge filesystem jobs into daemon state without resetting existing statuses."""
    state.setdefault("jobs", {})

    # Remove jobs whose files disappeared
    state["jobs"] = {
        job_id: info
        for job_id, info in state["jobs"].items()
        if Path(info.get("path", "")).exists()
    }

    # Add new job files as queued, but preserve existing job statuses
    if JOBS_DIR.exists():
        for path in sorted(JOBS_DIR.glob("*.md")):
            job_id = path.stem
            fm = read_job_frontmatter(path)
            if job_id not in state["jobs"]:
                state["jobs"][job_id] = {
                    "status": fm.get("status", "created"),
                    "path": str(path),
                    "created": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)
                    ),
                }
            else:
                # Update status from file if not terminal
                if state["jobs"][job_id]["status"] not in TERMINAL_STATUSES:
                    state["jobs"][job_id]["status"] = fm.get("status", state["jobs"][job_id]["status"])

    save_state(state)
    return state


def load_state() -> dict:
    """Load or reconcile daemon state."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            return reconcile_state(state)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse daemon state: {e}")
    return reconcile_state({"jobs": {}})


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
            ts = time.strftime("%Y%m%d%H%M%S", time.localtime())
            f.write(f"{ts}:{os.getpid()}")
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



def _is_pid_alive(pid: int) -> bool:
    """Check if a process is alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_lock_stale(job_id: str) -> bool:
    lock_path = LOCK_DIR / f"{job_id}.lock"
    if not lock_path.exists():
        return False
    try:
        content = lock_path.read_text(encoding="utf-8").strip()
        parts = content.split(":")
        if len(parts) != 2:
            return True
        ts_str, pid_str = parts
        lock_time = time.mktime(time.strptime(ts_str, "%Y%m%d%H%M%S"))
        age_min = (time.time() - lock_time) / 60
        pid = int(pid_str)
        pid_alive = _is_pid_alive(pid)

        # 生きているプロセスのロックは、年齢に関わらず絶対に奪わない
        if pid_alive:
            return False

        # 死んでいるプロセスのロックのみ、stale 判定を行う
        return age_min > STALE_MINUTES

    except (ValueError, OSError, TypeError) as e:
        logger.warning(f"Error checking lock status for {job_id}: {e}")
        return True


def reclaim_stale_lock(job_id: str) -> bool:
    """Remove a stale lock and acquire a new one."""
    if not is_lock_stale(job_id):
        return False
    lock_path = LOCK_DIR / f"{job_id}.lock"
    try:
        lock_path.unlink()
        return try_lock(job_id)
    except OSError as e:
        logger.error(f"Failed to reclaim stale lock for {job_id}: {e}")
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
    RUNNABLE_STATUSES = {"approved_gate_1", "approved_gate_3"}

    for job_id, job_info in state.get("jobs", {}).items():
        job_path = Path(job_info.get("path", ""))
        fm = read_job_frontmatter(job_path)
        job_status = fm.get("status", job_info.get("status", "created"))

        if job_status in TERMINAL_STATUSES:
            continue
        
        if job_status not in RUNNABLE_STATUSES:
            log_event("skip", job_id, f"waiting for Gate 1; status={job_status}")
            state["jobs"][job_id]["status"] = job_status
            save_state(state)
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
    state = load_state()
    save_state(state)
    log_event("startup", "daemon", f"{len(state['jobs'])} jobs queued")

    if args.once:
        processed = process_jobs()
        log_event("shutdown", "daemon", f"Processed {processed} jobs")
        return

    # Initialize Slack Adapter
    from apps.daemon.slack_adapter import AntigravitySlackAdapter
    slack_adapter = AntigravitySlackAdapter()
    slack_handler = slack_adapter.run_in_background()
    if slack_handler:
        logger.info("Slack Adapter started (Socket Mode)")

    # Continuous mode
    logger.info(f"Daemon started — watching {JOBS_DIR} (interval: {args.interval}s)")
    try:
        while True:
            # Check for jobs needing Slack notification (audit_passed)
            state = load_state()
            for jid, info in state.get("jobs", {}).items():
                if info.get("status") == "audit_passed":
                    # Determine artifact path (staging)
                    art_path = Path("work/artifacts/staging") / f"{jid}.md"
                    slack_adapter.send_audit_notification(jid, str(art_path))
            
            processed = process_jobs()
            if processed > 0:
                logger.info(f"  Processed {processed} jobs")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        if slack_handler:
            slack_handler.close()
        log_event("shutdown", "daemon", "SIGINT received")
        print("\nDaemon stopped")


if __name__ == "__main__":
    main()
