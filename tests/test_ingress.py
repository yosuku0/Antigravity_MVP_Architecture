import pytest
import time
from pathlib import Path
from apps.daemon.wiki_daemon import WikiDaemonHandler

def test_ingress_picking_up_new_job(tmp_repo, create_job, monkeypatch):
    """T011: Automated ingress from new markdown files."""
    # Mock graph to avoid execution
    monkeypatch.setattr("apps.runtime.graph.app.invoke", lambda state: {"audit_result": "pass"})
    
    handler = WikiDaemonHandler(
        jobs_dir=tmp_repo / "work" / "jobs",
        locks_dir=tmp_repo / "work" / "locks",
        logs_dir=tmp_repo / "runtime" / "logs"
    )
    
    # 1. Simulate a new job appearing
    job_path = create_job("JOB-NEW", "approved_gate_1")
    
    # 2. Call handler (normally called by watchdog, but we call it directly for test)
    handler.process_job(job_path)
    
    # 3. Assert transitioned to audit_passed
    content = job_path.read_text(encoding="utf-8")
    assert "status: audit_passed" in content
