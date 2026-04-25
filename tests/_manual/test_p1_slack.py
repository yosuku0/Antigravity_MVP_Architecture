import pytest
import os
from pathlib import Path
import yaml
from apps.ingress.slack_app import create_job_from_slack

def test_create_job_from_slack(tmp_path, monkeypatch):
    """Verify that create_job_from_slack creates a valid JOB file."""
    # Mock work/jobs directory to use tmp_path
    monkeypatch.chdir(tmp_path)
    (tmp_path / "work" / "jobs").mkdir(parents=True)
    
    text = "Implement Fibonacci"
    user = "U12345"
    
    job_id = create_job_from_slack(text, user)
    
    job_path = tmp_path / "work" / "jobs" / f"{job_id}.md"
    assert job_path.exists()
    
    content = job_path.read_text(encoding="utf-8")
    assert content.startswith("---")
    
    _, rest = content.split("---", 1)
    yaml_part, body = rest.split("---", 1)
    fm = yaml.safe_load(yaml_part)
    
    assert fm["job_id"] == job_id
    assert fm["status"] == "created"
    assert fm["source"] == "slack"
    assert fm["slack_user"] == user
    assert fm["objective"] == text
    assert text in body
