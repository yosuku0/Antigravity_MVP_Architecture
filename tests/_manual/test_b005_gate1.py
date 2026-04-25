import os
import sys
import subprocess
from pathlib import Path
import yaml

repo_root = Path(__file__).resolve().parents[2]
job_path = repo_root / "work" / "jobs" / "JOB-TEST-GATE1.md"
approve_script = repo_root / "scripts" / "approve.py"

# 1. Create a JOB with status: created
job_path.parent.mkdir(parents=True, exist_ok=True)
job_path.write_text("---\nstatus: created\n---\nBody", encoding="utf-8")

# 2. Run: python scripts/approve.py --job work/jobs/JOB-TEST-GATE1.md --gate 1
print("Running approve.py...")
result = subprocess.run(
    [sys.executable, str(approve_script), "--job", str(job_path), "--gate", "1"],
    capture_output=True, text=True
)

# 3. Assert exit code 0
success = True
if result.returncode != 0:
    print(f"FAIL: approve.py failed with exit code {result.returncode}")
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")
    success = False
else:
    print("PASS: approve.py exited with 0.")

# 4. Assert frontmatter status == approved_gate_1
def read_fm(p):
    t = p.read_text(encoding="utf-8")
    if not t.startswith("---"): return {}
    _, rest = t.split("---", 1)
    fm_part, _ = rest.split("---", 1)
    return yaml.safe_load(fm_part)

fm = read_fm(job_path)
if fm.get("status") != "approved_gate_1":
    print(f"FAIL: status is {fm.get('status')}, expected approved_gate_1")
    success = False
else:
    print("PASS: status is approved_gate_1.")

# 5. Assert frontmatter has approved_by and approved_at fields
if not fm.get("approved_by") or not fm.get("approved_at"):
    print("FAIL: approved_by or approved_at missing.")
    success = False
else:
    print(f"PASS: approved_by={fm.get('approved_by')}, approved_at={fm.get('approved_at')}")

# 6. Try to approve again → should fail
print("Running approve.py again (should fail)...")
result2 = subprocess.run(
    [sys.executable, str(approve_script), "--job", str(job_path), "--gate", "1"],
    capture_output=True, text=True
)
if result2.returncode == 0:
    print("FAIL: approve.py should have failed on already approved job.")
    success = False
else:
    print(f"PASS: approve.py failed as expected: {result2.stderr.strip()}")

# 7. Cleanup
if job_path.exists(): job_path.unlink()

if success:
    print("B-005 TEST PASSED")
    exit(0)
else:
    print("B-005 TEST FAILED")
    exit(1)
