import os
import time
import json
import yaml
from datetime import datetime, timezone
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

        self.log_event("job_claimed", job_id, {"message": "Atomic lock acquired"})
        
        # Transition status to claimed
        frontmatter["status"] = "claimed"
        try:
            write_frontmatter(job_path, frontmatter, body)
            print(f"Job {job_id} claimed and locked.")
        except Exception as e:
            print(f"Failed to write status for {job_id}: {e}")

def main():
    repo_root = Path(__file__).resolve().parents[2]
    jobs_dir = repo_root / "work" / "jobs"
    locks_dir = repo_root / "work" / "locks"
    logs_dir = repo_root / "runtime" / "logs"
    
    # Ensure directories exist
    jobs_dir.mkdir(parents=True, exist_ok=True)
    locks_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # TODO: B-002 State rebuild on startup
    # TODO: B-003 Stale-lock reclaim (background thread)

    handler = WikiDaemonHandler(jobs_dir, locks_dir, logs_dir)
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
