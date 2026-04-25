import os
import sys
import time
import json
import subprocess
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
jobs_dir = repo_root / "work" / "jobs"
locks_dir = repo_root / "work" / "locks"
logs_dir = repo_root / "runtime" / "logs"
daemon_script = repo_root / "apps" / "daemon" / "wiki_daemon.py"

# 1. Create 3 JOB files with different statuses
jobs_dir.mkdir(parents=True, exist_ok=True)
job1 = jobs_dir / "JOB-101.md"
job1.write_text("---\nstatus: approved_gate_1\n---\nBody 1", encoding="utf-8")
job2 = jobs_dir / "JOB-102.md"
job2.write_text("---\nstatus: claimed\n---\nBody 2", encoding="utf-8")
job3 = jobs_dir / "JOB-103.md"
job3.write_text("---\nstatus: executing\n---\nBody 3", encoding="utf-8")

# 2. Create 2 lock files
locks_dir.mkdir(parents=True, exist_ok=True)
lock1 = locks_dir / "JOB-102.lock"
lock1.write_text("2026-04-25T00:00:00Z\n1234\n", encoding="utf-8")
lock2 = locks_dir / "JOB-103.lock"
lock2.write_text("2026-04-25T00:00:05Z\n5678\n", encoding="utf-8")

# 3. Corrupt daemon_state.json
logs_dir.mkdir(parents=True, exist_ok=True)
state_cache = logs_dir / "daemon_state.json"
state_cache.write_text("{ invalid json", encoding="utf-8")

# 4. Restart daemon (run for a short time then stop)
print("Starting daemon for B-002 test...")
process = subprocess.Popen([sys.executable, str(daemon_script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(3)
process.terminate()
stdout, stderr = process.communicate()

print(stdout)
if stderr:
    print(f"Errors: {stderr}")

# 5. Assertions
success = True

# Check if daemon_state.json was fixed
try:
    with open(state_cache, "r", encoding="utf-8") as f:
        state = json.load(f)
    print("PASS: daemon_state.json rebuilt successfully.")
except Exception as e:
    print(f"FAIL: daemon_state.json not rebuilt or invalid: {e}")
    success = False

if success:
    if state.get("JOB-101", {}).get("status") != "approved_gate_1":
        print("FAIL: JOB-101 status incorrect.")
        success = False
    if state.get("JOB-102", {}).get("status") != "claimed":
        print("FAIL: JOB-102 status incorrect.")
        success = False
    if state.get("JOB-102", {}).get("pid") != 1234:
        print("FAIL: JOB-102 pid incorrect.")
        success = False
    if state.get("JOB-103", {}).get("pid") != 5678:
        print("FAIL: JOB-103 pid incorrect.")
        success = False

# Check logs
log_file = logs_dir / "daemon.jsonl"
if log_file.exists():
    log_content = log_file.read_text(encoding="utf-8")
    if "state_rebuilt" in log_content:
        print("PASS: state_rebuilt event found in logs.")
    else:
        print("FAIL: state_rebuilt event missing from logs.")
        success = False
else:
    print("FAIL: daemon.jsonl missing.")
    success = False

# Cleanup
for f in [job1, job2, job3, lock1, lock2]:
    if f.exists(): f.unlink()

if success:
    print("B-002 TEST PASSED")
    exit(0)
else:
    print("B-002 TEST FAILED")
    exit(1)
