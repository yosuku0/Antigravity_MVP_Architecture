"""
test_audit_promote.py — Audit + promote integration tests (updated for new stage/execute API).
"""
import pytest
import shutil
from pathlib import Path
from scripts.audit import audit_file
from scripts.promote import compute_hash, stage_job, execute_job as promote_execute_job
from utils.atomic_io import read_frontmatter, write_frontmatter
from unittest.mock import MagicMock


def test_audit_logic(tmp_path):
    """T006: Audit gate correctly detects syntax errors and secrets."""
    # Clean file
    clean_py = tmp_path / "clean.py"
    clean_py.write_text("print('ok')", encoding="utf-8")
    res = audit_file(clean_py)
    assert res["passed"] is True

    # File with secret
    secret_py = tmp_path / "secret.py"
    secret_py.write_text("api_key = 'nvapi-12345678901234567890'", encoding="utf-8")
    res = audit_file(secret_py)
    assert res["passed"] is False
    assert any("NVIDIA NIM" in f["description"] for f in res["findings"])


def test_compute_hash_full_sha256(tmp_path):
    """compute_hash must return a 64-char full SHA-256 hex digest."""
    f = tmp_path / "test.md"
    f.write_text("hello world", encoding="utf-8")
    h = compute_hash(f)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_stage_job_success(tmp_path, monkeypatch):
    """T012a: stage_job succeeds from approved_gate_2 state."""
    staging_dir = tmp_path / "work" / "artifacts" / "staging"
    staging_dir.mkdir(parents=True)
    import scripts.promote as promote_mod
    monkeypatch.setattr(promote_mod, "STAGING_DIR", staging_dir)

    art = tmp_path / "art.md"
    art.write_text("Wiki content", encoding="utf-8")

    job_path = tmp_path / "JOB-001.md"
    write_frontmatter(job_path, {
        "status": "approved_gate_2",
        "audit_result": "pass",
        "artifact_path": str(art),
        "job_id": "JOB-001",
    }, "Body")

    monkeypatch.chdir(tmp_path)
    assert stage_job(job_path) is True

    fm, _ = read_frontmatter(job_path)
    assert fm["status"] == "promotion_pending"
    assert len(fm["artifact_hash"]) == 64


def test_stage_job_denied_wrong_status(tmp_path, monkeypatch):
    """stage_job must fail if status != approved_gate_2."""
    staging_dir = tmp_path / "work" / "artifacts" / "staging"
    staging_dir.mkdir(parents=True)
    import scripts.promote as promote_mod
    monkeypatch.setattr(promote_mod, "STAGING_DIR", staging_dir)

    art = tmp_path / "art.md"
    art.write_text("content", encoding="utf-8")

    job_path = tmp_path / "JOB-002.md"
    write_frontmatter(job_path, {
        "status": "audit_passed",
        "audit_result": "pass",
        "artifact_path": str(art),
        "job_id": "JOB-002",
    }, "Body")

    monkeypatch.chdir(tmp_path)
    assert stage_job(job_path) is False

    fm, _ = read_frontmatter(job_path)
    assert fm["status"] == "audit_passed"  # unchanged


def test_execute_job_success(tmp_path, monkeypatch):
    """T012b: execute_job succeeds with valid staged artifact and mocked KnowledgeOS."""
    staging_dir = tmp_path / "work" / "artifacts" / "staging"
    staging_dir.mkdir(parents=True)
    import scripts.promote as promote_mod
    monkeypatch.setattr(promote_mod, "STAGING_DIR", staging_dir)

    staged = staging_dir / "JOB-003.md"
    staged.write_text("Final wiki", encoding="utf-8")
    h = compute_hash(staged)

    job_path = tmp_path / "JOB-003.md"
    write_frontmatter(job_path, {
        "status": "approved_gate_3",
        "audit_result": "pass",
        "approved_gate_2_by": "alice",
        "approved_gate_3_by": "bob",
        "staged_artifact_path": str(staged),
        "artifact_hash": h,
        "domain": "game",
        "topic": "my_topic",
        "job_id": "JOB-003",
    }, "Body")

    calls = []
    class FakeKnowledgeOS:
        def save(self, **kwargs):
            calls.append(kwargs)
            return f"domains/{kwargs['domain']}/wiki/{kwargs['topic']}.md"

    monkeypatch.setattr(promote_mod, "KnowledgeOS", FakeKnowledgeOS)
    monkeypatch.chdir(tmp_path)
    assert promote_execute_job(job_path) is True

    assert len(calls) == 1
    fm, _ = read_frontmatter(job_path)
    assert fm["status"] == "promoted"
    assert fm["promoted_hash"] == h
    assert "promoted_at" in fm
