import os
import sys
import time
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta

repo_root = Path(__file__).resolve().parents[2]
jobs_dir = repo_root / "work" / "jobs"
locks_dir = repo_root / "work" / "locks"
logs_dir = repo_root / "runtime" / "logs"
daemon_script = repo_root / "apps" / "daemon" / "wiki_daemon.py"

# Clean up EVERYTHING before test
job_path = jobs_dir / "JOB-STALE-001.md"
lock_path = locks_dir / "JOB-STALE-001.lock"
log_file = logs_dir / "daemon.jsonl"

if job_path.exists(): job_path.unlink()
if lock_path.exists(): lock_path.unlink()
if log_file.exists(): log_file.unlink()

# 1. Create a JOB with status executing
jobs_dir.mkdir(parents=True, exist_ok=True)
job_path.write_text("---\nstatus: executing\n---\nBody", encoding="utf-8")

# 2. Create a lock file with mtime artificially set to 11 minutes ago
locks_dir.mkdir(parents=True, exist_ok=True)
lock_path.write_text("2026-04-25T00:00:00Z\n9999\n", encoding="utf-8")

# Set mtime to 11 minutes ago
past_time = time.time() - (11 * 60)
os.utime(lock_path, (past_time, past_time))

print(f"Created stale lock at {lock_path} with mtime {datetime.fromtimestamp(past_time)}")

# 3. Start daemon
print("Starting daemon for B-003 test...")
process = subprocess.Popen([sys.executable, str(daemon_script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Wait for reclaim
reclaimed = False
for i in range(15):
    if not lock_path.exists():
        reclaimed = True
        print(f"Lock reclaimed after {i} seconds.")
        break
    time.sleep(1)

# Wait a bit more for status update and logging
time.sleep(2)

process.terminate()
stdout, stderr = process.communicate()

print("--- Daemon STDOUT ---")
print(stdout)
print("--- Daemon STDERR ---")
print(stderr)

# 4. Assertions
success = True

if not reclaimed:
    print("FAIL: Lock file still exists.")
    success = False
else:
    print("PASS: Lock file was reclaimed.")

# 5. Assert job status is appropriate
content = job_path.read_text(encoding="utf-8")
if "status: failed" not in content or "reason: stale_lock_recovered" not in content:
    print(f"FAIL: Job status not changed to failed with reason. Content: {content}")
    success = False
else:
    print("PASS: Job status changed to failed correctly.")

# 6. Assert daemon.jsonl has stale_lock_recovered event
if log_file.exists():
    log_content = log_file.read_text(encoding="utf-8")
    if "stale_lock_recovered" in log_content:
        print("PASS: stale_lock_recovered event found in logs.")
    else:
        print(f"FAIL: stale_lock_recovered event missing from logs. Logs: {log_content}")
        success = False
else:
    print("FAIL: daemon.jsonl missing.")
    success = False

# 7. Cleanup
if job_path.exists(): job_path.unlink()
archived_dir = locks_dir / "archived"
if archived_dir.exists():
    for f in archived_dir.glob("JOB-STALE-001*.lock"):
        f.unlink()

if success:
    print("B-003 TEST PASSED")
    exit(0)
else:
    print("B-003 TEST FAILED")
    exit(1)
