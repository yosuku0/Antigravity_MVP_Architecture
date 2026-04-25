import pytest
import shutil
from pathlib import Path
import yaml
from scripts.audit import audit_artifact
from scripts.promote import stage_promotion, promote_to_wiki

def test_audit_logic(tmp_path):
    # Clean
    clean_py = tmp_path / "clean.py"
    clean_py.write_text("print('ok')", encoding="utf-8")
    res = audit_artifact(clean_py)
    assert res["result"] == "pass"
    
    # Secret
    secret_py = tmp_path / "secret.py"
    secret_py.write_text("api_key = 'sk-12345678901234567890'", encoding="utf-8")
    res = audit_artifact(secret_py)
    assert res["result"] == "fail"
    assert "Secret pattern detected" in res["errors"][0]

def test_promotion_flow(tmp_repo, create_job, monkeypatch):
    # Setup: Approved Gate 2 job
    job_id = "JOB-PROMOTE"
    job_path = create_job(job_id, "audit_passed", audit_result="pass", approved_gate_2_by="tester")
    
    # Setup: Raw file
    raw_file = tmp_repo / "raw" / "wiki_page.md"
    raw_file.write_text("Wiki Content", encoding="utf-8")
    
    # 1. Stage
    stage_promotion(job_path, repo_root=tmp_repo)
    with open(job_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f.read().split("---")[1])
    assert data["status"] == "promotion_pending"
    assert (tmp_repo / "work" / "artifacts" / "staging" / job_id / "wiki_page.md").exists()
    
    # 2. Gate 3 Approval (manual status update in job for test)
    data["status"] = "approved_gate_3"
    data["approved_gate_3_by"] = "tester"
    from utils.atomic_io import atomic_write
    yaml_text = yaml.dump(data, sort_keys=False)
    atomic_write(job_path, f"---\n{yaml_text}---\n\nBody")
    
    # 3. Promote
    # Mock hermes_reflect subprocess to avoid error
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MagicMock())
    
    promote_to_wiki(job_path, "tester", repo_root=tmp_repo)
    assert (tmp_repo / "wiki" / "wiki_page.md").exists()
    with open(job_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f.read().split("---")[1])
    assert data["status"] == "promoted"

from unittest.mock import MagicMock
