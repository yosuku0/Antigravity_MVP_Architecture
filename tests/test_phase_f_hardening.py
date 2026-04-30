import json
from pathlib import Path

import pytest

import apps.daemon.wiki_daemon as daemon_mod
from scripts.monitor_gpu import parse_nvidia_smi_csv
from utils.cli_operations import build_cli_operation, validate_cli_operation
from utils.atomic_io import read_frontmatter


@pytest.fixture(autouse=True)
def redirect_daemon_globals(tmp_repo, monkeypatch):
    monkeypatch.chdir(tmp_repo)
    monkeypatch.setattr(daemon_mod, "JOBS_DIR", tmp_repo / "work" / "jobs")
    monkeypatch.setattr(daemon_mod, "LOCK_DIR", tmp_repo / "work" / "locks")
    monkeypatch.setattr(daemon_mod, "STATE_FILE", tmp_repo / "work" / "daemon_state.json")
    monkeypatch.setattr(daemon_mod, "LOG_FILE", tmp_repo / "work" / "daemon.jsonl")


def test_reconcile_recovers_running_job_and_persists_retry(tmp_repo, create_job):
    job_path = create_job("JOB-RECOVER", "approved_gate_1")
    previous = {
        "jobs": {
            "JOB-RECOVER": {
                "status": "running",
                "last_known_status": "approved_gate_1",
                "path": str(job_path),
                "retry_count": 0,
                "frozen": False,
            }
        }
    }

    state = daemon_mod.reconcile_state(previous)

    entry = state["jobs"]["JOB-RECOVER"]
    assert entry["status"] == "approved_gate_1"
    assert entry["last_known_status"] == "approved_gate_1"
    assert entry["retry_count"] == 1
    assert entry["frozen"] is False
    fm, _ = read_frontmatter(job_path)
    assert fm["retry_count"] == 1


def test_reconcile_freezes_job_after_retry_limit(tmp_repo, create_job, monkeypatch):
    monkeypatch.setattr(daemon_mod, "MAX_RETRIES", 1)
    job_path = create_job("JOB-FREEZE", "approved_gate_1", retry_count=1)
    previous = {
        "jobs": {
            "JOB-FREEZE": {
                "status": "running",
                "last_known_status": "approved_gate_1",
                "path": str(job_path),
                "retry_count": 1,
                "frozen": False,
            }
        }
    }

    state = daemon_mod.reconcile_state(previous)

    entry = state["jobs"]["JOB-FREEZE"]
    assert entry["retry_count"] == 2
    assert entry["frozen"] is True
    fm, _ = read_frontmatter(job_path)
    assert fm["frozen"] is True
    assert fm["freeze_reason"] == "retry_limit_exceeded"


def test_cli_operation_validator_blocks_direct_wiki_write():
    operation = build_cli_operation(
        cli="codex",
        action="write",
        target_path="domains/game/wiki/notes.md",
        outcome="success",
        actor="tester",
    )
    assert "wiki writes must go through promote.py" in validate_cli_operation(operation)


def test_cli_operation_validator_allows_promote_wiki_write():
    operation = build_cli_operation(
        cli="promote.py",
        action="promote",
        target_path="domains/game/wiki/notes.md",
        outcome="success",
        actor="tester",
    )
    assert validate_cli_operation(operation) == []


def test_scope_guard_validates_cli_operation_log(tmp_repo):
    log_dir = tmp_repo / "logs"
    log_dir.mkdir()
    bad = {
        "ts": "2026-04-30T00:00:00Z",
        "cli": "codex",
        "actor": "tester",
        "action": "write",
        "target_path": "wiki/index.md",
        "outcome": "success",
    }
    (log_dir / "cli_operations.jsonl").write_text(json.dumps(bad) + "\n", encoding="utf-8")

    findings = daemon_mod.PROJECT_ROOT  # keep import graph stable for coverage tools
    from scripts.scope_guard import scan_cli_operation_logs

    findings = scan_cli_operation_logs(tmp_repo)
    assert findings
    assert "wiki writes must go through promote.py" in findings[0]["reason"]


def test_parse_nvidia_smi_csv():
    output = "0, NVIDIA RTX, 12, 2048, 8192, 55, 66.5\n"
    rows = parse_nvidia_smi_csv(output, "2026-04-30T00:00:00Z")
    assert rows == [{
        "ts": "2026-04-30T00:00:00Z",
        "index": "0",
        "name": "NVIDIA RTX",
        "utilization_gpu_percent": "12",
        "memory_used_mib": "2048",
        "memory_total_mib": "8192",
        "temperature_gpu_c": "55",
        "power_draw_w": "66.5",
    }]
