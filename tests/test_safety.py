import pytest
import yaml
from scripts.audit import audit_file
from scripts.approve import approve_gate_1

def test_t016_secret_leak_audit(tmp_path, tmp_repo, create_job):
    """T016: Secret leak detection in audit_file."""
    # 1. Job with secret pattern
    f1 = tmp_path / "leak.py"
    f1.write_text("api_key = 'nvapi-12345678901234567890'", encoding="utf-8")
    res = audit_file(f1)
    assert res["passed"] is False
    assert any("NVIDIA NIM" in f["description"] for f in res["findings"])
    
    # 2. Human rejection
    job_path = create_job("JOB-T016-REJECT", "audit_passed")
    from scripts.approve import approve_gate_2
    approve_gate_2(job_path, approver="higurashi", reject=True)
    
    parts = job_path.read_text(encoding="utf-8").split("---")
    fm = yaml.safe_load(parts[1])
    assert fm["status"] == "gate_2_rejected"
    assert fm["gate_2_rejected_by"] == "higurashi"

def test_t015_idempotent_rerun(tmp_repo, create_job):
    """T015: Idempotent re-run of previously failed job."""
    job_path = create_job("JOB-T015", "failed")
    
    # Re-running means setting it back to created
    content = job_path.read_text(encoding="utf-8")
    parts = content.split("---")
    fm = yaml.safe_load(parts[1])
    body = parts[2]
    
    fm["status"] = "created"
    from utils.atomic_io import atomic_write
    atomic_write(job_path, f"---\n{yaml.dump(fm)}---\n\n{body}")
    
    # Verify status
    new_content = job_path.read_text(encoding="utf-8")
    new_fm = yaml.safe_load(new_content.split("---")[1])
    assert new_fm["status"] == "created"
