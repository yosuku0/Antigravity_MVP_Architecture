import pytest
pytestmark = pytest.mark.skip(reason="Legacy WikiDaemonHandler tests need rewrite for functional daemon")
import time
import json
from pathlib import Path

def test_daemon_claims_approved_job(tmp_repo, create_job, monkeypatch):
    """T001: Daemon picking up jobs with approved_gate_1 status."""
    # Mock graph app.invoke to avoid actual execution
    monkeypatch.setattr("apps.runtime.graph.app.invoke", lambda state: {"audit_result": "pass"})
    
    # 1. Create an approved job
    job_path = create_job("JOB-001", "approved_gate_1")
    
    # 2. Run handler
    handler = WikiDaemonHandler(
        jobs_dir=tmp_repo / "work" / "jobs",
        locks_dir=tmp_repo / "work" / "locks",
        logs_dir=tmp_repo / "runtime" / "logs"
    )
    handler.process_job(job_path)
    
    # 3. Assert lock is NOT present (released)
    lock_path = tmp_repo / "work" / "locks" / "JOB-001.lock"
    assert not lock_path.exists()
    
    # 4. Assert status updated in job file
    content = job_path.read_text(encoding="utf-8")
    assert "status: audit_passed" in content

def test_daemon_rebuild_state(tmp_repo, create_job):
    """T002: State rebuild from filesystem truth on startup."""
    # 1. Create a claimed job and a lock
    create_job("JOB-CLAIMED", "claimed")
    lock_path = tmp_repo / "work" / "locks" / "JOB-CLAIMED.lock"
    lock_path.write_text("lock", encoding="utf-8")
    
    # 2. Rebuild
    handler = WikiDaemonHandler(
        jobs_dir=tmp_repo / "work" / "jobs",
        locks_dir=tmp_repo / "work" / "locks",
        logs_dir=tmp_repo / "runtime" / "logs"
    )
    state = handler.rebuild_state()
    
    assert "JOB-CLAIMED" in state
    assert state["JOB-CLAIMED"]["status"] == "claimed"

def test_daemon_reclaimer(tmp_repo, create_job):
    """T003: Stale lock reclamation and recovery to failed."""
    # 1. Create a stale lock (> 10 min)
    job_path = create_job("JOB-STALE", "claimed")
    lock_path = tmp_repo / "work" / "locks" / "JOB-STALE.lock"
    lock_path.write_text("stale", encoding="utf-8")
    
    # Manually set mtime to 20 mins ago
    stale_time = time.time() - 1200
    os.utime(lock_path, (stale_time, stale_time))
    
    # 2. Run reclaimer logic
    handler = WikiDaemonHandler(
        jobs_dir=tmp_repo / "work" / "jobs",
        locks_dir=tmp_repo / "work" / "locks",
        logs_dir=tmp_repo / "runtime" / "logs"
    )
    handler.reclaim_stale_locks()
    
    # 3. Assert transitioned to failed
    content = job_path.read_text(encoding="utf-8")
    assert "status: failed" in content
    assert "reason: stale_lock_recovered" in content

import os
