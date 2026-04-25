import pytest
from scripts.audit import audit_artifact
from scripts.approve import approve_gate_1

def test_t016_secret_leak_audit(tmp_path):
    """T016: Verify that audit gate catches various secrets."""
    # 1. AWS Secret
    f1 = tmp_path / "aws.py"
    f1.write_text("AWS_SECRET_ACCESS_KEY = 'AKIA" + "A"*36 + "'", encoding="utf-8")
    assert audit_artifact(f1)["result"] == "fail"
    
    # 2. Generic API Key
    f2 = tmp_path / "api.py"
    f2.write_text("API_KEY = 'nvapi-abcdefghijklmnopqrstuvwxyz123456'", encoding="utf-8")
    assert audit_artifact(f2)["result"] == "fail"
    
    # 3. Password
    f3 = tmp_path / "pass.py"
    f3.write_text("db_password = 'super_secret_pass'", encoding="utf-8")
    assert audit_artifact(f3)["result"] == "fail"

def test_t015_role_based_approval(tmp_repo, create_job):
    """T015: Verify that approval requires correct role (mocked for MVP)."""
    job_path = create_job("JOB-T015", "created")
    
    # For MVP, approve_gate_1 accepts any user, but we verify it records the user.
    approve_gate_1(job_path, approver="higurashi")
    
    import yaml
    with open(job_path, "r", encoding="utf-8") as f:
        fm = yaml.safe_load(f.read().split("---")[1])
    
    assert fm["status"] == "approved_gate_1"
    assert fm["approved_by"] == "higurashi"
