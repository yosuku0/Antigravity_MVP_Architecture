import os
import sys
from pathlib import Path

# Ensure we can import audit_node from apps.runtime.graph
repo_root = Path(__file__).resolve().parents[2]
sys.path.append(str(repo_root))

from apps.runtime.graph import audit_node

def test_audit_node():
    success = True
    temp_dir = repo_root / "work" / "temp_audit"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Create a clean artifact.py
    clean_path = temp_dir / "clean.py"
    clean_path.write_text("def hello():\n    print('hello')\n", encoding="utf-8")
    
    print("Testing clean artifact...")
    state = {"artifact_path": str(clean_path)}
    res = audit_node(state)
    if res["audit_result"] != "pass":
        print(f"FAIL: Clean artifact failed audit: {res.get('audit_errors')}")
        success = False
    else:
        print("PASS: Clean artifact passed.")

    # 2. Create an artifact with a fake secret
    secret_path = temp_dir / "secret.py"
    # AWS Secret Access Key pattern is 40 chars
    secret_path.write_text("AWS_SECRET_ACCESS_KEY='AKIA123456789012345678901234567890123456'\n", encoding="utf-8")
    
    print("Testing secret artifact...")
    state = {"artifact_path": str(secret_path)}
    res = audit_node(state)
    if res["audit_result"] != "fail":
        print("FAIL: Secret artifact passed audit.")
        success = False
    else:
        print(f"PASS: Secret artifact failed as expected: {res.get('audit_errors')}")

    # 3. Create an artifact with syntax error
    bad_path = temp_dir / "bad.py"
    bad_path.write_text("def hello(\n    print('hello')\n", encoding="utf-8")
    
    print("Testing syntax error artifact...")
    state = {"artifact_path": str(bad_path)}
    res = audit_node(state)
    if res["audit_result"] != "fail":
        print("FAIL: Syntax error artifact passed audit.")
        success = False
    else:
        print(f"PASS: Syntax error artifact failed as expected: {res.get('audit_errors')}")

    # Cleanup
    for f in [clean_path, secret_path, bad_path]:
        if f.exists(): f.unlink()
    if temp_dir.exists(): temp_dir.rmdir()
    
    if success:
        print("B-007 TEST PASSED")
        exit(0)
    else:
        print("B-007 TEST FAILED")
        exit(1)

if __name__ == "__main__":
    test_audit_node()
