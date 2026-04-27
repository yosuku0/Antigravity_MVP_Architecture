"""
test_daemon.py — Daemon state management tests (updated for new parallel API).

Note on reconcile_state: load_state() calls reconcile_state() which re-reads
JOB frontmatter. To test daemon dispatch, we verify dispatch count and log
rather than the reconciled status (which reflects JOB frontmatter, not daemon state).
"""
import pytest
import time
import json
import os
from pathlib import Path
import apps.daemon.wiki_daemon as daemon_mod
from apps.daemon.wiki_daemon import rebuild_state, process_jobs_parallel, load_state, save_state
from utils.atomic_io import write_frontmatter


class SyncExecutor:
    """Executor that runs tasks synchronously for deterministic testing."""
    def submit(self, fn, *args):
        fn(*args)


@pytest.fixture(autouse=True)
def redirect_daemon_globals(tmp_repo, monkeypatch):
    """Redirect all daemon file-system globals to the tmp_repo."""
    monkeypatch.chdir(tmp_repo)
    monkeypatch.setattr(daemon_mod, "JOBS_DIR", tmp_repo / "work" / "jobs")
    monkeypatch.setattr(daemon_mod, "LOCK_DIR", tmp_repo / "work" / "locks")
    monkeypatch.setattr(daemon_mod, "STATE_FILE", tmp_repo / "work" / "daemon_state.json")
    monkeypatch.setattr(daemon_mod, "LOG_FILE", tmp_repo / "work" / "daemon.jsonl")


def test_daemon_rebuild_state(tmp_repo, create_job):
    """T002: State rebuild from filesystem truth."""
    create_job("JOB-DAEMON", "created")
    state = rebuild_state()
    assert "JOB-DAEMON" in state["jobs"]
    assert state["jobs"]["JOB-DAEMON"]["status"] == "created"


def test_daemon_process_jobs_dispatches(tmp_repo, create_job, monkeypatch):
    """T001: Daemon dispatches exactly 1 job when approved_gate_1 is present."""
    create_job("JOB-PROCESS", "approved_gate_1")

    dispatched = []
    def mock_execute(job_id, job_path, status):
        dispatched.append({"job_id": job_id, "status": status})
        # Also update the JOB frontmatter to simulate graph completion
        jp = Path(job_path)
        fm, body = __import__("utils.atomic_io", fromlist=["read_frontmatter"]).read_frontmatter(jp)
        fm["status"] = "audit_passed"
        write_frontmatter(jp, fm, body)
        return {"status": "audit_passed", "audit_result": "pass"}

    monkeypatch.setattr(daemon_mod, "execute_job", mock_execute)

    count = process_jobs_parallel(SyncExecutor())
    assert count == 1
    assert len(dispatched) == 1
    assert dispatched[0]["status"] == "approved_gate_1"

    # After frontmatter update, reconciled state should show audit_passed
    state = load_state()
    assert state["jobs"]["JOB-PROCESS"]["status"] == "audit_passed"


def test_daemon_stale_lock_recovery(tmp_repo, create_job, monkeypatch):
    """T003: Stale lock reclamation for dead PIDs."""
    job_id = "JOB-STALE"
    create_job(job_id, "approved_gate_1")

    lock_dir = tmp_repo / "work" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{job_id}.lock"
    stale_ts = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time() - 1200))
    lock_path.write_text(f"{stale_ts}:99999", encoding="utf-8")

    dispatched = []
    def mock_execute(job_id, job_path, status):
        dispatched.append(job_id)
        jp = Path(job_path)
        fm, body = __import__("utils.atomic_io", fromlist=["read_frontmatter"]).read_frontmatter(jp)
        fm["status"] = "audit_passed"
        write_frontmatter(jp, fm, body)
        return {"status": "audit_passed"}

    monkeypatch.setattr(daemon_mod, "execute_job", mock_execute)

    process_jobs_parallel(SyncExecutor())

    # Lock should be released
    assert not lock_path.exists()
    # Job was dispatched despite stale lock
    assert job_id in dispatched
    # Status updated via frontmatter
    state = load_state()
    assert state["jobs"][job_id]["status"] == "audit_passed"
