import os
import time
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class WikiDaemonHandler(FileSystemEventHandler):
    def __init__(self, jobs_dir, locks_dir, logs_dir):
        self.jobs_dir = Path(jobs_dir)
        self.locks_dir = Path(locks_dir)
        self.logs_dir = Path(logs_dir)
        self.log_file = self.logs_dir / "daemon.jsonl"
        
    def log_event(self, event_type, job_id, details=None):
        event = {"type": event_type, "job_id": job_id, "timestamp": time.time()}
        if details:
            event["details"] = details
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.md'):
            return
        self.process_job(Path(event.src_path))

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.md'):
            return
        self.process_job(Path(event.src_path))

    def process_job(self, job_path: Path):
        # TODO: Implement robust frontmatter reading
        content = job_path.read_text(encoding="utf-8")
        if "status: approved_gate_1" not in content.lower():
            return

        job_id = job_path.stem
        lock_path = self.locks_dir / f"{job_id}.lock"

        # Atomic lock acquisition
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, b"LOCKED")
            os.close(fd)
        except FileExistsError:
            # Lock already exists, another process took it
            return

        self.log_event("CLAIMED", job_id, "Atomic lock acquired")
        
        # TODO: Implement state transition to `claimed` (update frontmatter)
        # TODO: Trigger graph execution
        print(f"Job {job_id} claimed and locked.")

def main():
    repo_root = Path(__file__).resolve().parents[2]
    jobs_dir = repo_root / "work" / "jobs"
    locks_dir = repo_root / "work" / "locks"
    logs_dir = repo_root / "runtime" / "logs"
    
    # Ensure directories exist
    jobs_dir.mkdir(parents=True, exist_ok=True)
    locks_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    handler = WikiDaemonHandler(jobs_dir, locks_dir, logs_dir)
    observer = Observer()
    observer.schedule(handler, str(jobs_dir), recursive=False)
    observer.start()
    
    print(f"Wiki Daemon listening on {jobs_dir}...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
