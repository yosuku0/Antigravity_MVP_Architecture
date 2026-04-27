"""
test_hitl.py — HITL approval CLI tests (updated for new state-aware approve.py API).
"""
import pytest
import subprocess
import sys
from pathlib import Path
from utils.atomic_io import read_frontmatter, write_frontmatter

PROJECT_ROOT = Path(__file__).parent.parent


def _fm(job_path: Path) -> dict:
    fm, _ = read_frontmatter(job_path)
    return fm


def _make_job(tmp_repo, job_id: str, status: str) -> Path:
    path = tmp_repo / "work" / "jobs" / f"{job_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(path, {"status": status, "job_id": job_id}, "Body")
    return path


def _approve(job_path, gate, approver="tester", reject=False, reason=""):
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "approve.py"),
           "--gate", str(gate), "--approver", approver, "--job", str(job_path)]
    if reject:
        cmd += ["--reject", "--reason", reason]
    return subprocess.run(cmd, capture_output=True, text=True,
                          cwd=str(PROJECT_ROOT), check=False)


def test_gate_2_approval(tmp_repo, monkeypatch):
    """Gate 2 approval: audit_passed -> approved_gate_2."""
    job_path = _make_job(tmp_repo, "JOB-G2-APPROVE", "audit_passed")
    result = _approve(job_path, 2)
    assert result.returncode == 0, result.stderr
    assert _fm(job_path)["status"] == "approved_gate_2"


def test_gate_2_rejection(tmp_repo, monkeypatch):
    """Gate 2 rejection: audit_passed -> gate_2_rejected."""
    job_path = _make_job(tmp_repo, "JOB-G2-REJECT", "audit_passed")
    result = _approve(job_path, 2, reject=True, reason="bad content")
    assert result.returncode == 0, result.stderr
    assert _fm(job_path)["status"] == "gate_2_rejected"


def test_gate_3_approval(tmp_repo, monkeypatch):
    """Gate 3 approval: promotion_pending -> approved_gate_3."""
    job_path = _make_job(tmp_repo, "JOB-G3-APPROVE", "promotion_pending")
    result = _approve(job_path, 3)
    assert result.returncode == 0, result.stderr
    assert _fm(job_path)["status"] == "approved_gate_3"


def test_gate_2_denied_from_wrong_state(tmp_repo, monkeypatch):
    """Gate 2 must be denied when status is not audit_passed."""
    job_path = _make_job(tmp_repo, "JOB-G2-DENY", "audit_failed")
    result = _approve(job_path, 2)
    assert result.returncode != 0
    assert _fm(job_path)["status"] == "audit_failed"


def test_cancellation(tmp_repo, create_job, monkeypatch):
    """T009: Job cancellation via cancel.py."""
    monkeypatch.chdir(tmp_repo)
    job_id = "JOB-CANCEL"
    job_path = create_job(job_id, "approved_gate_1")

    lock_path = tmp_repo / "work" / "locks" / f"{job_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("lock", encoding="utf-8")

    staging_dir = tmp_repo / "work" / "artifacts" / "staging" / job_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    from scripts.cancel import cancel_job
    cancel_job(job_path, repo_root=tmp_repo)

    data = _fm(job_path)
    assert data["status"] == "cancelled"
    assert not lock_path.exists()
    assert not staging_dir.exists()
