import pytest
import shutil
from pathlib import Path
import yaml
from scripts.audit import audit_file
from scripts.promote import compute_hash

def test_audit_logic(tmp_path):
    """T006: Audit gate correctly detects syntax errors and secrets."""
    # Clean
    clean_py = tmp_path / "clean.py"
    clean_py.write_text("print('ok')", encoding="utf-8")
    res = audit_file(clean_py)
    assert res["passed"] is True
    
    # Secret
    secret_py = tmp_path / "secret.py"
    secret_py.write_text("api_key = 'nvapi-12345678901234567890'", encoding="utf-8")
    res = audit_file(secret_py)
    assert res["passed"] is False
    assert any("NVIDIA NIM" in f["description"] for f in res["findings"])

from scripts.promote import promote_file

def test_promotion_flow(tmp_repo, monkeypatch):
    """T012: Full promotion flow using promote_file."""
    monkeypatch.chdir(tmp_repo)
    
    # Setup: Artifact in staging
    staging_dir = Path("work/artifacts/staging")
    staging_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = staging_dir / "wiki_page.md"
    artifact_path.write_text("Wiki Content", encoding="utf-8")
    
    # Setup: Job file with approvals
    job_path = Path("work/jobs/wiki_page.md")
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text("---\nstatus: approved_gate_1\napproved_gate_2_by: dev\napproved_gate_3_by: mgr\n---\nBody", encoding="utf-8")

    # Mock Gate 3 approval (input returns 'y')
    monkeypatch.setattr("builtins.input", lambda _: "y")
    
    # Promote to work/wiki (default)
    res = promote_file(artifact_path)
    assert res == 0
    assert Path("work/wiki/wiki_page.md").exists()
    
    # Verify content and frontmatter
    promoted_content = Path("work/wiki/wiki_page.md").read_text(encoding="utf-8")
    assert "topic: wiki_page" in promoted_content
    assert "Wiki Content" in promoted_content

from unittest.mock import MagicMock
