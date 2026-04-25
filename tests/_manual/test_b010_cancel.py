import os
import sys
import subprocess
import yaml
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
job_path = repo_root / "work" / "jobs" / "JOB-TEST-CANCEL.md"
lock_path = repo_root / "work" / "locks" / "JOB-TEST-CANCEL.lock"
staging_dir = repo_root / "work" / "artifacts" / "staging" / "JOB-TEST-CANCEL"
cancel_script = repo_root / "scripts" / "cancel.py"

def read_fm(p):
    t = p.read_text(encoding="utf-8")
    if not t.startswith("---"): return {}
    _, rest = t.split("---", 1)
    fm_part, _ = rest.split("---", 1)
    return yaml.safe_load(fm_part)

def test_cancel():
    success = True
    
    # 1. Create a JOB with status: approved_gate_1
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text("---\nstatus: approved_gate_1\n---\nBody", encoding="utf-8")
    
    # 2. Create a lock file
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("lock", encoding="utf-8")
    
    # 3. Create staged artifacts
    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "temp.txt").write_text("temp", encoding="utf-8")
    
    # 4. Run: python scripts/cancel.py --job ...
    print("Cancelling job...")
    subprocess.run([sys.executable, str(cancel_script), "--job", str(job_path)], check=True)
    
    # 5. Assert status == cancelled
    fm = read_fm(job_path)
    if fm.get("status") != "cancelled":
        print(f"FAIL: Expected status cancelled, got {fm.get('status')}")
        success = False
    else:
        print("PASS: Status is cancelled.")
        
    # 6. Assert lock removed
    if lock_path.exists():
        print("FAIL: Lock file still exists.")
        success = False
    else:
        print("PASS: Lock removed.")
        
    # 7. Assert staged artifacts purged
    if staging_dir.exists():
        print("FAIL: Staging directory still exists.")
        success = False
    else:
        print("PASS: Staging purged.")

    # Cleanup
    if job_path.exists(): job_path.unlink()
    
    if success:
        print("B-010 TEST PASSED")
        exit(0)
    else:
        print("B-010 TEST FAILED")
        exit(1)

if __name__ == "__main__":
    test_cancel()
