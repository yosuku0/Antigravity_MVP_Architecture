import os
import sys
import time
import subprocess
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
jobs_dir = repo_root / "work" / "jobs"
locks_dir = repo_root / "work" / "locks"
logs_dir = repo_root / "runtime" / "logs"
daemon_script = repo_root / "apps" / "daemon" / "wiki_daemon.py"

jobs_dir.mkdir(parents=True, exist_ok=True)
locks_dir.mkdir(parents=True, exist_ok=True)
logs_dir.mkdir(parents=True, exist_ok=True)

job_path = jobs_dir / "JOB-001.md"
lock_path = locks_dir / "JOB-001.lock"
log_path = logs_dir / "daemon.jsonl"

# Cleanup before test
if job_path.exists(): os.remove(job_path)
if lock_path.exists(): os.remove(lock_path)

# 1. Start daemon
print("Starting wiki_daemon.py...")
process = subprocess.Popen([sys.executable, str(daemon_script)])
time.sleep(2) # Give it time to start watching

# 2. Create a dummy JOB-001.md
with open(job_path, "w", encoding="utf-8") as f:
    f.write("---\nstatus: approved_gate_1\n---\nDummy body")

print("Created JOB-001.md")
time.sleep(3) # Give it time to process

# 6. Stop daemon
process.terminate()
process.wait()

# Verify
success = True

# 3. Verify lock file
if not lock_path.exists():
    print("FAIL: Lock file not created!")
    success = False
else:
    print("PASS: Lock file exists.")

# 4. Verify JOB-001.md status
content = job_path.read_text(encoding="utf-8")
if "status: claimed" not in content:
    print("FAIL: Job status not changed to claimed!")
    success = False
else:
    print("PASS: Job status is claimed.")

# 5. Verify daemon.jsonl
if not log_path.exists():
    print("FAIL: daemon.jsonl not created!")
    success = False
else:
    logs = log_path.read_text(encoding="utf-8")
    if "job_claimed" not in logs or "JOB-001" not in logs:
        print("FAIL: daemon.jsonl missing claim event!")
        success = False
    else:
        print("PASS: daemon.jsonl logged claim event.")

# 7. Cleanup
if job_path.exists(): os.remove(job_path)
if lock_path.exists(): os.remove(lock_path)

if success:
    print("B-001 TEST PASSED")
    exit(0)
else:
    print("B-001 TEST FAILED")
    exit(1)
