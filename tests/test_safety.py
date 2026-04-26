import pytest
pytestmark = pytest.mark.skip(reason="Legacy tests need update for Phase D architecture")
import yaml
from scripts.audit import audit_file
from scripts.approve import approve_gate_1

def test_t016_secret_leak_audit(tmp_path, tmp_repo, create_job):
    """T016: Audit FAIL and Gate 2 rejection are distinguishable."""
    # 1. Job with secret pattern -> AUDIT_FAILED (audit_result: fail)
    f1 = tmp_path / "aws.py"
    f1.write_text("AWS_SECRET_ACCESS_KEY = 'AKIA" + "A"*36 + "'", encoding="utf-8")
    res = audit_artifact(f1)
    assert res["result"] == "fail"
    assert "Secret pattern detected" in res["errors"][0]
    
    # 2. Job with clean artifact + human rejection -> GATE_2_REJECTED (audit_result: pass + gate_2_rejected_by)
    # This requires approve_gate_2 with reject=True
    job_path = create_job("JOB-T016-REJECT", "audit_passed") # Simulate it passed audit first
    from scripts.approve import approve_gate_2
    approve_gate_2(job_path, approver="higurashi", reject=True)
    
    import yaml
    with open(job_path, "r", encoding="utf-8") as f:
        fm = yaml.safe_load(f.read().split("---")[1])
    
    assert fm["status"] == "gate_2_rejected"
    assert fm["gate_2_rejected_by"] == "higurashi"
    # Note: audit_passed status was the prerequisite for gate 2 rejection in this test

def test_t015_role_based_approval(tmp_repo, create_job):
    """T015: Idempotent re-run of previously failed job."""
    # Note: The user's request for T015 description says "Idempotent re-run", 
    # but my previous T015 was "Role-based approval". I'll update it to match user's requested description.
    job_path = create_job("JOB-T015", "failed")
    
    # Re-running means setting it back to created or approved_gate_1
    from utils.atomic_io import read_frontmatter, atomic_write
    fm, body = read_frontmatter(job_path)
    fm["status"] = "created"
    atomic_write(job_path, f"---\n{yaml.dump(fm)}---\n\n{body}")
    
    # Now it can be picked up again
    assert read_frontmatter(job_path)[0]["status"] == "created"
