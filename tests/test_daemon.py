import pytest
import time
import json
import os
from pathlib import Path
from apps.daemon.wiki_daemon import rebuild_state, process_jobs, load_state, save_state

def test_daemon_rebuild_state(tmp_repo, create_job, monkeypatch):
    """T002: State rebuild from filesystem truth."""
    monkeypatch.chdir(tmp_repo)
    
    # 1. Create a job file
    create_job("JOB-DAEMON", "created")
    
    # 2. Rebuild
    state = rebuild_state()
    assert "JOB-DAEMON" in state["jobs"]
    assert state["jobs"]["JOB-DAEMON"]["status"] == "queued"

def test_daemon_process_jobs(tmp_repo, create_job, monkeypatch):
    """T001: Daemon processing queued jobs."""
    monkeypatch.chdir(tmp_repo)
    
    # 1. Create a job
    job_path = create_job("JOB-PROCESS", "queued")
    
    # Mock apps.runtime.graph.app.invoke to avoid actual execution
    # and return a mock result
    mock_result = {"status": "done", "audit_result": "pass"}
    monkeypatch.setattr("apps.daemon.wiki_daemon.execute_job", lambda j, p: mock_result)
    
    # 2. Process
    count = process_jobs()
    assert count == 1
    
    # 3. Verify state
    state = load_state()
    assert state["jobs"]["JOB-PROCESS"]["status"] == "done"

def test_daemon_stale_lock_recovery(tmp_repo, create_job, monkeypatch):
    """T003: Stale lock reclamation."""
    monkeypatch.chdir(tmp_repo)
    
    # 1. Create a job and a stale lock
    job_id = "JOB-STALE"
    create_job(job_id, "queued")
    
    lock_dir = Path("work/locks")
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{job_id}.lock"
    lock_path.write_text("dead-pid", encoding="utf-8")
    
    # Set mtime to 20 mins ago
    stale_time = time.time() - 1200
    os.utime(lock_path, (stale_time, stale_time))
    
    # 2. Process jobs - it should reclaim and run
    mock_result = {"status": "done"}
    monkeypatch.setattr("apps.daemon.wiki_daemon.execute_job", lambda j, p: mock_result)
    
    process_jobs()
    
    # 3. Verify it was processed
    state = load_state()
    assert state["jobs"][job_id]["status"] == "done"
    assert not lock_path.exists()
