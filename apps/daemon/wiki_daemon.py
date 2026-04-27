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
import threading
import concurrent.futures
import subprocess
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

GRAPH_RUNNABLE_STATUSES = {"approved_gate_1"}
PROMOTION_STATUSES = {"approved_gate_2", "approved_gate_3"}
ALL_RUNNABLE_STATUSES = GRAPH_RUNNABLE_STATUSES | PROMOTION_STATUSES


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


class PathEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Path objects."""
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def save_state(state: dict) -> None:
    """Atomically save daemon state."""
    atomic_write(STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False, cls=PathEncoder))


# Global lock for state.json access
STATE_LOCK = threading.Lock()

def update_job_status_safe(job_id: str, status: str, result: dict = None, error: str = None) -> None:
    """Thread-safe update of job status in daemon state."""
    with STATE_LOCK:
        state = load_state()
        if job_id in state["jobs"]:
            state["jobs"][job_id]["status"] = status
            if result:
                state["jobs"][job_id]["result"] = result
            if error:
                state["jobs"][job_id]["error"] = error
            save_state(state)
            logger.debug(f"Status updated to {status}", extra={"job_id": job_id})


def worker_task(job_id: str, job_path: str, original_status: str) -> None:
    """
    Worker task to execute a job in parallel.
    Ensures lock release and thread-safe status updates.
    
    Note on status handling:
    - Graph jobs (approved_gate_1): marked as 'running' during execution.
    - Promotion jobs (approved_gate_2/3): NOT marked as 'running'. JOB frontmatter
      is the SSOT. daemon_state is updated only after subprocess exits.
    """
    try:
        logger.info(f"Worker started execution", extra={"job_id": job_id, "original_status": original_status})
        log_event("start", job_id)
        
        # 1. Only mark 'running' for Graph-based jobs.
        # Promotion subprocesses are short-lived and use JOB frontmatter as SSOT.
        if original_status in GRAPH_RUNNABLE_STATUSES:
            update_job_status_safe(job_id, "running")
        else:
            logger.debug(f"Promotion job: not marking 'running', keeping original status", extra={"job_id": job_id})

        # 2. Execute job
        result = execute_job(job_id, job_path, original_status)

        # 3. Finalize status in daemon_state.
        final_status = result.get("status", "unknown")
        update_job_status_safe(job_id, final_status, result=result)

        if result.get("promotion_error"):
            log_event("promotion_error", job_id, f"returncode={result.get('returncode')} stderr={result.get('stderr', '')[:200]}")
            logger.warning(f"Promotion failed, daemon_state preserved as '{final_status}'", extra={"job_id": job_id})
        else:
            detail = result.get("audit_result", "") or result.get("stdout", "") or result.get("error", "")
            log_event("complete", job_id, detail)
            logger.info(f"Worker finished with status: {final_status}", extra={"job_id": job_id})

    except Exception as e:
        logger.error(f"Worker crashed: {e}", extra={"job_id": job_id}, exc_info=True)
        # Only fall through to 'failed' for unexpected Python exceptions (not promote.py failures).
        if original_status in GRAPH_RUNNABLE_STATUSES:
            update_job_status_safe(job_id, "failed", error=str(e))
        else:
            # For promotion jobs: preserve original status so the job can be retried.
            update_job_status_safe(job_id, original_status, error=str(e))
        log_event("error", job_id, str(e))
    finally:
        # Always release the lock
        release_lock(job_id)
        logger.debug(f"Lock released", extra={"job_id": job_id})


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


def run_promote_command(job_path: str, mode: str, original_status: str) -> dict:
    """Run promote.py in a safe subprocess.
    
    On success: returns target status (promotion_pending or promoted).
    On failure: returns original_status to preserve daemon_state as non-terminal.
                JOB frontmatter is NOT modified (promote.py handles that).
    """
    try:
        cmd = [
            sys.executable,
            "scripts/promote.py",
            "--job",
            str(job_path),
            "--mode",
            mode,
        ]
        logger.info(f"Running promotion subprocess", extra={"mode": mode, "job_path": str(job_path)})
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if proc.returncode == 0:
            # Success: promote.py already updated JOB frontmatter.
            target_status = "promotion_pending" if mode == "stage" else "promoted"
            logger.info(f"Promotion succeeded -> {target_status}", extra={"mode": mode})
            return {
                "status": target_status,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            }
        else:
            # Failure: promote.py is fail-close and did NOT modify JOB frontmatter.
            # Return original_status so daemon_state stays non-terminal and retryable.
            logger.error(
                f"Promotion subprocess failed (code {proc.returncode})",
                extra={"mode": mode, "stdout": proc.stdout, "stderr": proc.stderr}
            )
            return {
                "status": original_status,
                "promotion_error": True,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
    except Exception as e:
        logger.error(f"Failed to launch promotion process: {e}")
        return {
            "status": original_status,
            "promotion_error": True,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }


def execute_job(job_id: str, job_path: str, original_status: str) -> dict:
    """Branch execution between Graph and Promote CLI."""
    if original_status in GRAPH_RUNNABLE_STATUSES:
        try:
            from apps.runtime.graph import run_job
            result = run_job(job_path, job_id)
            return result
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    if original_status == "approved_gate_2":
        return run_promote_command(job_path, mode="stage", original_status=original_status)
    
    if original_status == "approved_gate_3":
        return run_promote_command(job_path, mode="execute", original_status=original_status)

    return {"status": "failed", "error": f"Invalid status for execution: {original_status}"}


def process_jobs_parallel(executor: concurrent.futures.ThreadPoolExecutor) -> int:
    """
    Dispatcher: Process all queued jobs by submitting them to a thread pool.
    Returns number of jobs dispatched.
    """
    state = load_state()
    count = 0
    for job_id, job_info in state.get("jobs", {}).items():
        job_path = Path(job_info.get("path", ""))
        fm = read_job_frontmatter(job_path)
        job_status = fm.get("status", job_info.get("status", "created"))

        if job_status in TERMINAL_STATUSES or job_status == "running":
            continue
        
        if job_status not in ALL_RUNNABLE_STATUSES:
            # We don't log skip anymore to keep dispatcher logs clean
            continue

        # Try to acquire lock
        if not try_lock(job_id):
            if is_lock_stale(job_id):
                if not reclaim_stale_lock(job_id):
                    continue
            else:
                continue

        # Dispatch to executor
        logger.info(f"Dispatching job to worker pool ({job_status})", extra={"job_id": job_id})
        executor.submit(worker_task, job_id, str(job_path), job_status)
        count += 1

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

    # Parallel workers configuration
    MAX_WORKERS = int(os.environ.get("MAX_WORKERS", 4))
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
    logger.info(f"Initialized thread pool with {MAX_WORKERS} workers")

    if args.once:
        processed = process_jobs_parallel(executor)
        log_event("shutdown", "daemon", f"Dispatched {processed} jobs")
        executor.shutdown(wait=True)
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
            # Gate 2 Slack notification: send only when audit_passed and not yet notified.
            state = load_state()
            for jid, info in state.get("jobs", {}).items():
                job_path = Path(info.get("path", ""))
                if not job_path.exists():
                    continue
                fm = read_job_frontmatter(job_path)

                # Only notify for audit_passed jobs
                if fm.get("status") != "audit_passed":
                    continue

                # Dedup: slack_adapter writes slack_ts on success; skip if already notified.
                if fm.get("slack_ts"):
                    continue

                # Use the artifact_path recorded in JOB frontmatter (not staging path —
                # staging does not exist yet at audit_passed stage).
                artifact_path = fm.get("artifact_path")
                if not artifact_path or not Path(artifact_path).exists():
                    logger.warning(
                        "Skipping Slack Gate 2 notification: artifact_path missing or not found",
                        extra={"job_id": jid, "artifact_path": artifact_path},
                    )
                    continue

                slack_adapter.send_audit_notification(jid, str(artifact_path))
            
            processed = process_jobs_parallel(executor)
            if processed > 0:
                logger.info(f"  Dispatched {processed} jobs")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        if slack_handler:
            slack_handler.close()
        logger.info("Shutting down executor...")
        executor.shutdown(wait=True)
        log_event("shutdown", "daemon", "SIGINT received")
        print("\nDaemon stopped")


if __name__ == "__main__":
    main()
