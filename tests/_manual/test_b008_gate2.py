import os
import sys
import subprocess
import yaml
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
job_path = repo_root / "work" / "jobs" / "JOB-TEST-GATE2.md"
approve_script = repo_root / "scripts" / "approve.py"

def read_fm(p):
    t = p.read_text(encoding="utf-8")
    if not t.startswith("---"): return {}
    _, rest = t.split("---", 1)
    fm_part, _ = rest.split("---", 1)
    return yaml.safe_load(fm_part)

def test_gate2():
    success = True
    
    # 1. Create a JOB with status: audit_passed
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text("---\nstatus: audit_passed\n---\nBody", encoding="utf-8")
    
    # 2. Run: python scripts/approve.py --job ... --gate 2
    print("Approving Gate 2...")
    subprocess.run([sys.executable, str(approve_script), "--job", str(job_path), "--gate", "2"], check=True)
    
    fm = read_fm(job_path)
    if fm.get("status") != "approved_gate_2":
        print(f"FAIL: Expected approved_gate_2, got {fm.get('status')}")
        success = False
    else:
        print("PASS: Gate 2 approved.")

    # 3. Create another JOB with status: audit_passed
    job_path.write_text("---\nstatus: audit_passed\n---\nBody", encoding="utf-8")
    
    # 4. Run: python scripts/approve.py --job ... --gate 2 --reject
    print("Rejecting Gate 2...")
    subprocess.run([sys.executable, str(approve_script), "--job", str(job_path), "--gate", "2", "--reject"], check=True)
    
    fm = read_fm(job_path)
    if fm.get("status") != "gate_2_rejected":
        print(f"FAIL: Expected gate_2_rejected, got {fm.get('status')}")
        success = False
    else:
        print("PASS: Gate 2 rejected correctly.")

    # 5. Try to approve a job with status != audit_passed
    job_path.write_text("---\nstatus: created\n---\nBody", encoding="utf-8")
    print("Testing approval on wrong status (should fail)...")
    res = subprocess.run([sys.executable, str(approve_script), "--job", str(job_path), "--gate", "2"], capture_output=True, text=True)
    if res.returncode == 0:
        print("FAIL: Should have failed on 'created' status for Gate 2.")
        success = False
    else:
        print(f"PASS: Failed as expected: {res.stderr.strip()}")

    # Cleanup
    if job_path.exists(): job_path.unlink()
    
    if success:
        print("B-008 TEST PASSED")
        exit(0)
    else:
        print("B-008 TEST FAILED")
        exit(1)

if __name__ == "__main__":
    test_gate2()
