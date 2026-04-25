import pytest
import subprocess
import sys
import yaml
from pathlib import Path
from scripts.approve import approve_gate_1, approve_gate_2, approve_gate_3
from scripts.cancel import cancel_job

def test_gate_1_approval(tmp_repo, create_job):
    job_path = create_job("JOB-G1", "created")
    approve_gate_1(job_path, "tester")
    
    with open(job_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f.read().split("---")[1])
    assert data["status"] == "approved_gate_1"
    assert data["approved_by"] == "tester"

def test_gate_2_rejection(tmp_repo, create_job):
    job_path = create_job("JOB-G2", "audit_passed")
    approve_gate_2(job_path, "tester", reject=True)
    
    with open(job_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f.read().split("---")[1])
    assert data["status"] == "gate_2_rejected"

def test_cancellation(tmp_repo, create_job):
    job_id = "JOB-CANCEL"
    job_path = create_job(job_id, "approved_gate_1")
    
    # Create a lock and staging
    lock_path = tmp_repo / "work" / "locks" / f"{job_id}.lock"
    lock_path.write_text("lock", encoding="utf-8")
    
    staging_dir = tmp_repo / "work" / "artifacts" / "staging" / job_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    cancel_job(job_path, repo_root=tmp_repo)
    
    with open(job_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f.read().split("---")[1])
    assert data["status"] == "cancelled"
    assert not lock_path.exists()
    assert not staging_dir.exists()
