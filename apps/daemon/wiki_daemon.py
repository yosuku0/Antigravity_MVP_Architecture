import os
import time
import json
import yaml
import shutil
from datetime import datetime, timezone, timedelta
from threading import Thread
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import sys

# Ensure utils can be imported
sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.atomic_io import read_frontmatter, write_frontmatter

class WikiDaemonHandler(PatternMatchingEventHandler):
    def __init__(self, jobs_dir, locks_dir, logs_dir):
        super().__init__(patterns=["*.md"], ignore_directories=True)
        self.jobs_dir = Path(jobs_dir)
        self.locks_dir = Path(locks_dir)
        self.logs_dir = Path(logs_dir)
        self.log_file = self.logs_dir / "daemon.jsonl"
        self.daemon_state = {}
        
    def log_event(self, event_type, job_id, details=None):
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "job_id": job_id,
            "pid": os.getpid()
        }
        if details:
            event.update(details)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def rebuild_state(self):
        """Rebuild ground truth state from filesystem."""
        print("Rebuilding daemon state...")
        self.daemon_state = {}
        
        # 1. Scan jobs
        jobs_found = 0
        for job_file in self.jobs_dir.glob("*.md"):
            try:
                frontmatter, _ = read_frontmatter(job_file)
                job_id = job_file.stem
                self.daemon_state[job_id] = {
                    "status": frontmatter.get("status"),
                    "job_path": str(job_file)
                }
                jobs_found += 1
            except Exception as e:
                print(f"Error reading job {job_file}: {e}")

        # 2. Scan locks
        locks_found = 0
        for lock_file in self.locks_dir.glob("*.lock"):
            job_id = lock_file.stem
            if job_id not in self.daemon_state:
                self.daemon_state[job_id] = {"status": "unknown"}
            
            try:
                content = lock_file.read_text().splitlines()
                if len(content) >= 2:
                    self.daemon_state[job_id].update({
                        "lock_path": str(lock_file),
                        "claimed_at": content[0],
                        "pid": int(content[1])
                    })
                locks_found += 1
            except Exception as e:
                print(f"Error reading lock {lock_file}: {e}")

        # 3. Log event
        self.log_event("state_rebuilt", "system", {
            "jobs_found": jobs_found,
            "locks_found": locks_found
        })
        
        # 4. Update cache file
        state_cache = self.logs_dir / "daemon_state.json"
        try:
            with open(state_cache, "w", encoding="utf-8") as f:
                json.dump(self.daemon_state, f, indent=2)
        except Exception as e:
            print(f"Error writing state cache: {e}")
            
        print(f"State rebuilt: {jobs_found} jobs, {locks_found} locks found.")
        return self.daemon_state

    def update_job_status(self, job_id, new_status, reason=None):
        """Helper to update job status atomically."""
        job_path = self.jobs_dir / f"{job_id}.md"
        if not job_path.exists():
            return
            
        try:
            frontmatter, body = read_frontmatter(job_path)
            frontmatter["status"] = new_status
            if reason:
                frontmatter["failure_reason"] = reason
            write_frontmatter(job_path, frontmatter, body)
            
            # Update in-memory state
            if job_id in self.daemon_state:
                self.daemon_state[job_id]["status"] = new_status
        except Exception as e:
            print(f"Error updating status for {job_id}: {e}")

    def is_pid_alive(self, pid):
        """Check if a process is alive (Windows-compatible)."""
        import subprocess
        try:
            # tasklist returns 0 if found, 1 if not found
            res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
            return str(pid) in res.stdout
        except:
            return False

    def reclaim_stale_locks(self):
        """Check and reclaim locks older than 10 minutes OR orphaned by dead processes."""
        now = datetime.now(timezone.utc)
        for lock_file in self.locks_dir.glob("*.lock"):
            try:
                # Read lock info
                content = lock_file.read_text().splitlines()
                pid = None
                if len(content) >= 2:
                    pid = int(content[1])
                
                # Get file age
                mtime = datetime.fromtimestamp(lock_file.stat().st_mtime, tz=timezone.utc)
                
                is_stale = (now - mtime > timedelta(minutes=10))
                is_orphaned = (pid is not None and pid != os.getpid() and not self.is_pid_alive(pid))
                
                if is_stale or is_orphaned:
                    job_id = lock_file.stem
                    
                    # T014/T003 distinction:
                    lock_age_minutes = (now - mtime).total_seconds() / 60
                    if lock_age_minutes < 10:
                        # Recent lock = daemon crash during execution (T014)
                        reason = "no_checkpoint"
                    else:
                        # Old lock = stale lock reclaim (T003)
                        reason = "stale_lock_recovered"
                        
                    print(f"Reclaiming lock for {job_id} (Reason: {reason}, PID: {pid})...")
                    
                    # 1. Archive
                    archive_dir = self.locks_dir / "archived"
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = now.strftime("%Y%m%d%H%M%S")
                    archive_path = archive_dir / f"{job_id}_{timestamp}.lock"
                    shutil.move(str(lock_file), str(archive_path))
                    
                    # 2. Update status
                    # Scan frontmatter to be sure
                    job_path = self.jobs_dir / f"{job_id}.md"
                    if job_path.exists():
                        fm, _ = read_frontmatter(job_path)
                        status = fm.get("status")
                        if status in ["claimed", "executing", "routed"]:
                            self.update_job_status(job_id, "failed", reason=reason)
                        else:
                            # If it was already finished but lock stayed, just archive lock
                            pass
                    
                    # 3. Log
                    self.log_event("lock_recovered", job_id, {
                        "reason": reason,
                        "archived_to": str(archive_path), 
                        "pid": pid,
                        "age_min": round(lock_age_minutes, 2)
                    })
            except Exception as e:
                print(f"Error reclaiming lock {lock_file}: {e}")

    def on_created(self, event):
        self.process_job(Path(event.src_path))

    def on_modified(self, event):
        self.process_job(Path(event.src_path))

    def process_job(self, job_path: Path):
        try:
            frontmatter, body = read_frontmatter(job_path)
        except Exception as e:
            print(f"Error parsing {job_path}: {e}")
            return
            
        status = frontmatter.get("status")
        if status in ["promoted", "failed", "cancelled"]:
            return
            
        if status != "approved_gate_1":
            return

        job_id = job_path.stem
        lock_path = self.locks_dir / f"{job_id}.lock"

        # Atomic lock acquisition
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w') as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()}\n{os.getpid()}\n")
        except FileExistsError:
            # Lock already exists, another process took it
            return

        try:
            self.log_event("job_claimed", job_id, {"message": "Atomic lock acquired"})
            self.daemon_state[job_id] = {
                "status": "claimed",
                "lock_path": str(lock_path),
                "claimed_at": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid()
            }
            
            # Transition status to claimed
            frontmatter["status"] = "claimed"
            write_frontmatter(job_path, frontmatter, body)
            print(f"Job {job_id} claimed and locked. Executing...")
            
            # Execute graph
            from apps.runtime.graph import app
            inputs = {"job_path": str(job_path)}
            result = app.invoke(inputs)
            
            # Update status based on audit result
            audit_res = result.get("audit_result")
            new_status = "audit_passed" if audit_res == "pass" else "audit_failed"
            self.update_job_status(job_id, new_status)
            print(f"Job {job_id} finished: {new_status}")
            
            # P1-002: Slack notification for Gate 2
            if new_status == "audit_passed":
                from apps.ingress.slack_notifier import notify_gate
                slack_user = frontmatter.get("slack_user")
                if slack_user:
                    notify_gate(job_id, gate=2, slack_user=slack_user)
            
        except Exception as e:
            print(f"Failed to execute job {job_id}: {e}")
            self.update_job_status(job_id, "failed", reason=str(e))
        finally:
            # Release lock
            if lock_path.exists():
                os.remove(lock_path)
                print(f"Lock released for {job_id}")

def main():
    repo_root = Path(__file__).resolve().parents[2]
    jobs_dir = repo_root / "work" / "jobs"
    locks_dir = repo_root / "work" / "locks"
    logs_dir = repo_root / "runtime" / "logs"
    
    # Ensure directories exist
    jobs_dir.mkdir(parents=True, exist_ok=True)
    locks_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # B-002: State rebuild on startup
    handler = WikiDaemonHandler(jobs_dir, locks_dir, logs_dir)
    handler.rebuild_state()
    handler.reclaim_stale_locks()

    # B-003: Stale-lock reclaim (background thread)
    def reclaimer_loop():
        while True:
            try:
                handler.reclaim_stale_locks()
            except Exception as e:
                print(f"Error in reclaimer loop: {e}")
            time.sleep(60)

    reclaimer_thread = Thread(target=reclaimer_loop, daemon=True)
    reclaimer_thread.start()
    observer = Observer()
    observer.schedule(handler, str(jobs_dir), recursive=False)
    observer.start()
    
    print(f"Wiki Daemon listening on {jobs_dir}...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Wiki Daemon...")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
