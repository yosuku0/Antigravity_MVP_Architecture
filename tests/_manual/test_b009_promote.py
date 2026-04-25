import os
import sys
import subprocess
import yaml
import shutil
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
job_path = repo_root / "work" / "jobs" / "JOB-TEST-PROMOTE.md"
raw_dir = repo_root / "raw"
wiki_dir = repo_root / "wiki"
promote_script = repo_root / "scripts" / "promote.py"
approve_script = repo_root / "scripts" / "approve.py"

def read_fm(p):
    t = p.read_text(encoding="utf-8")
    if not t.startswith("---"): return {}
    _, rest = t.split("---", 1)
    fm_part, _ = rest.split("---", 1)
    return yaml.safe_load(fm_part)

def test_promote():
    success = True
    
    # 0. Prep raw/
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "test.txt").write_text("Hello Wiki", encoding="utf-8")
    
    # 1. Create a JOB with audit_result: pass and approved_gate_2_by: higurashi
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text("---\nstatus: audit_passed\naudit_result: pass\napproved_gate_2_by: higurashi\n---\nBody", encoding="utf-8")
    
    # 2. Run: python scripts/promote.py --job ... --stage
    print("Staging promotion...")
    subprocess.run([sys.executable, str(promote_script), "--job", str(job_path), "--stage"], check=True)
    
    fm = read_fm(job_path)
    if fm.get("status") != "promotion_pending":
        print(f"FAIL: Expected promotion_pending, got {fm.get('status')}")
        success = False
    else:
        print("PASS: Staged correctly.")

    # 3. Run: python scripts/approve.py --job ... --gate 3
    print("Approving Gate 3...")
    subprocess.run([sys.executable, str(approve_script), "--job", str(job_path), "--gate", "3"], check=True)
    
    fm = read_fm(job_path)
    if fm.get("status") != "approved_gate_3":
        print(f"FAIL: Expected approved_gate_3, got {fm.get('status')}")
        success = False
    else:
        print("PASS: Gate 3 approved.")

    # 4. Run: python scripts/promote.py --job ... --promote
    print("Promoting to wiki...")
    subprocess.run([sys.executable, str(promote_script), "--job", str(job_path), "--promote"], check=True)
    
    if not (wiki_dir / "test.txt").exists():
        print("FAIL: test.txt not found in wiki/")
        success = False
    else:
        print("PASS: File promoted to wiki/.")

    # 5. Assert final status == promoted
    fm = read_fm(job_path)
    if fm.get("status") != "promoted":
        print(f"FAIL: Expected status promoted, got {fm.get('status')}")
        success = False
    else:
        print("PASS: Final status is promoted.")

    # Cleanup
    if job_path.exists(): job_path.unlink()
    if (raw_dir / "test.txt").exists(): (raw_dir / "test.txt").unlink()
    if (wiki_dir / "test.txt").exists(): (wiki_dir / "test.txt").unlink()
    shutil.rmtree(repo_root / "work" / "artifacts" / "staging" / "JOB-TEST-PROMOTE", ignore_errors=True)
    
    if success:
        print("B-009 TEST PASSED")
        exit(0)
    else:
        print("B-009 TEST FAILED")
        exit(1)

if __name__ == "__main__":
    test_promote()
