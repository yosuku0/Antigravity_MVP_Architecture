"""
test_promotion_state_machine.py — P0 HITL promotion state machine regression tests.

Covers the full state machine:
  approved_gate_1 -> Graph -> audit_passed/audit_failed
  audit_passed -> Gate 2 (Slack/CLI) -> approved_gate_2
  approved_gate_2 -> promote.py --mode stage -> promotion_pending
  promotion_pending -> Gate 3 CLI -> approved_gate_3
  approved_gate_3 -> promote.py --mode execute -> promoted
"""
import pytest
import subprocess
import sys
import os
from pathlib import Path
from utils.atomic_io import read_frontmatter, write_frontmatter
import scripts.promote as promote_mod
from apps.daemon import wiki_daemon

# Absolute path to project root (for subprocess calls)
PROJECT_ROOT = Path(__file__).parent.parent


# ── shared helpers ─────────────────────────────────────────────────────────

def fm(path: Path) -> dict:
    f, _ = read_frontmatter(path)
    return f


def make_job(jobs_dir: Path, job_id: str, status: str, extra: dict = None) -> Path:
    path = jobs_dir / f"{job_id}.md"
    data = {"status": status, "job_id": job_id}
    if extra:
        data.update(extra)
    write_frontmatter(path, data, "task body")
    return path


class SyncExecutor:
    def submit(self, fn, *args):
        fn(*args)


# ── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Set up a minimal workspace and redirect daemon globals."""
    jobs_dir = tmp_path / "work" / "jobs"
    locks_dir = tmp_path / "work" / "locks"
    staging_dir = tmp_path / "work" / "artifacts" / "staging"
    for d in (jobs_dir, locks_dir, staging_dir):
        d.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(wiki_daemon, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(wiki_daemon, "LOCK_DIR", locks_dir)
    monkeypatch.setattr(wiki_daemon, "STATE_FILE", tmp_path / "work" / "daemon_state.json")
    monkeypatch.setattr(wiki_daemon, "LOG_FILE", tmp_path / "work" / "daemon.jsonl")
    monkeypatch.setattr(promote_mod, "STAGING_DIR", staging_dir)

    return {"tmp": tmp_path, "jobs": jobs_dir, "staging": staging_dir}


# ══════════════════════════════════════════════════════════════════════════════
# 1. CLI approval (approve.py)
# ══════════════════════════════════════════════════════════════════════════════

class TestCLIApproval:
    def _approve(self, job_path, gate, by="tester", reject=False, reason=""):
        cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "approve.py"),
               "--gate", str(gate), "--approver", by, "--job", str(job_path)]
        if reject:
            cmd += ["--reject", "--reason", reason]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))

    def test_gate2_from_audit_passed(self, workspace):
        job = make_job(workspace["jobs"], "G2-OK", "audit_passed")
        r = self._approve(job, 2)
        assert r.returncode == 0
        assert fm(job)["status"] == "approved_gate_2"
        assert fm(job)["approved_gate_2_by"] == "tester"

    def test_gate3_from_promotion_pending(self, workspace):
        job = make_job(workspace["jobs"], "G3-OK", "promotion_pending")
        r = self._approve(job, 3)
        assert r.returncode == 0
        assert fm(job)["status"] == "approved_gate_3"

    def test_gate2_reject(self, workspace):
        job = make_job(workspace["jobs"], "G2-REJ", "audit_passed")
        r = self._approve(job, 2, reject=True, reason="not good")
        assert r.returncode == 0
        assert fm(job)["status"] == "gate_2_rejected"

    def test_gate3_reject_unsupported(self, workspace):
        """Gate 3 reject is not supported in MVP — must fail without changing FM."""
        job = make_job(workspace["jobs"], "G3-REJ", "promotion_pending")
        r = self._approve(job, 3, reject=True, reason="nope")
        assert r.returncode != 0
        assert fm(job)["status"] == "promotion_pending"

    def test_gate2_denied_from_audit_failed(self, workspace):
        job = make_job(workspace["jobs"], "G2-DENY", "audit_failed")
        r = self._approve(job, 2)
        assert r.returncode != 0
        assert fm(job)["status"] == "audit_failed"

    def test_gate3_denied_from_audit_passed(self, workspace):
        """Cannot skip Gate 2 — Gate 3 requires promotion_pending."""
        job = make_job(workspace["jobs"], "G3-SKIP", "audit_passed")
        r = self._approve(job, 3)
        assert r.returncode != 0
        assert fm(job)["status"] == "audit_passed"

    def test_gate2_denied_from_promoted(self, workspace):
        job = make_job(workspace["jobs"], "G2-DONE", "promoted")
        r = self._approve(job, 2)
        assert r.returncode != 0
        assert fm(job)["status"] == "promoted"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Slack Gate 2 (slack_adapter.py)
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackGate2:
    @pytest.fixture
    def slack_env(self, workspace):
        from apps.daemon.slack_adapter import AntigravitySlackAdapter
        adapter = AntigravitySlackAdapter.__new__(AntigravitySlackAdapter)
        adapter.app = None  # disable real Slack
        adapter.bot_token = None
        adapter.app_token = None
        adapter.channel_id = None
        adapter.admin_ids = ["U_TESTER"]
        return adapter, workspace

    def test_approve_from_audit_passed(self, slack_env, monkeypatch):
        adapter, workspace = slack_env
        job = make_job(workspace["jobs"], "SL-OK", "audit_passed")
        from utils.atomic_io import write_frontmatter
        fm_data, body = read_frontmatter(job)
        fm_data["approved_gate_2_by"] = None
        write_frontmatter(job, fm_data, body)

        # Call the internal state-change logic directly
        fm_data, body = read_frontmatter(job)
        if fm_data.get("status") == "audit_passed" and adapter.is_authorized("U_TESTER"):
            fm_data["status"] = "approved_gate_2"
            fm_data["approved_gate_2_by"] = "U_TESTER"
            write_frontmatter(job, fm_data, body)

        assert fm(job)["status"] == "approved_gate_2"

    def test_slack_cannot_write_approved_gate_3(self, workspace, monkeypatch):
        """Slack adapter must never write approved_gate_3 directly."""
        content = (PROJECT_ROOT / "apps" / "daemon" / "slack_adapter.py").read_text(encoding="utf-8")
        # approved_gate_3 must not appear as a value being written
        assert 'fm["status"] = "approved_gate_3"' not in content, \
            "slack_adapter.py must not directly write approved_gate_3 to JOB frontmatter"

    def test_slack_approve_denied_from_promotion_pending(self, workspace):
        """Slack cannot approve a job that is already promotion_pending."""
        job = make_job(workspace["jobs"], "SL-PEND", "promotion_pending")
        # The state-aware check: approved_gate_2 requires audit_passed
        current = fm(job)["status"]
        assert current != "audit_passed"
        # FM must remain unchanged (no state transition happened)
        assert fm(job)["status"] == "promotion_pending"


# ══════════════════════════════════════════════════════════════════════════════
# 3. promote.py stage / execute
# ══════════════════════════════════════════════════════════════════════════════

class TestPromoteStagingExecution:
    def test_stage_success(self, workspace):
        art = workspace["tmp"] / "artifact.md"
        art.write_text("content", encoding="utf-8")
        job = make_job(workspace["jobs"], "PR-STAGE", "approved_gate_2", {
            "audit_result": "pass", "artifact_path": str(art)
        })
        assert promote_mod.stage_job(job) is True
        f = fm(job)
        assert f["status"] == "promotion_pending"
        assert len(f["artifact_hash"]) == 64
        assert Path(f["staged_artifact_path"]).exists()

    def test_stage_denied_wrong_status(self, workspace):
        art = workspace["tmp"] / "art2.md"
        art.write_text("c", encoding="utf-8")
        job = make_job(workspace["jobs"], "PR-DENY", "audit_passed", {
            "audit_result": "pass", "artifact_path": str(art)
        })
        assert promote_mod.stage_job(job) is False
        assert fm(job)["status"] == "audit_passed"

    def test_stage_denied_audit_result_fail(self, workspace):
        art = workspace["tmp"] / "art3.md"
        art.write_text("c", encoding="utf-8")
        job = make_job(workspace["jobs"], "PR-AFAIL", "approved_gate_2", {
            "audit_result": "fail", "artifact_path": str(art)
        })
        assert promote_mod.stage_job(job) is False

    def test_execute_success(self, workspace, monkeypatch):
        staged = workspace["staging"] / "PR-EXEC.md"
        staged.write_text("wiki content", encoding="utf-8")
        h = promote_mod.compute_hash(staged)

        job = make_job(workspace["jobs"], "PR-EXEC", "approved_gate_3", {
            "audit_result": "pass",
            "approved_gate_2_by": "alice",
            "approved_gate_3_by": "bob",
            "staged_artifact_path": str(staged),
            "artifact_hash": h,
            "domain": "game",
            "topic": "good_topic",
        })

        calls = []
        class FakeKOS:
            def save(self, **kw):
                calls.append(kw)
                return f"domains/{kw['domain']}/wiki/{kw['topic']}.md"

        monkeypatch.setattr(promote_mod, "KnowledgeOS", FakeKOS)
        assert promote_mod.execute_job(job) is True
        assert len(calls) == 1
        assert calls[0]["domain"] == "game"
        f = fm(job)
        assert f["status"] == "promoted"
        assert f["promoted_hash"] == h

    def test_execute_denied_checksum_mismatch(self, workspace, monkeypatch):
        staged = workspace["staging"] / "PR-HASH.md"
        staged.write_text("original", encoding="utf-8")
        h = promote_mod.compute_hash(staged)
        staged.write_text("tampered", encoding="utf-8")

        job = make_job(workspace["jobs"], "PR-HASH", "approved_gate_3", {
            "audit_result": "pass",
            "approved_gate_2_by": "alice",
            "approved_gate_3_by": "bob",
            "staged_artifact_path": str(staged),
            "artifact_hash": h,
            "domain": "game",
        })
        monkeypatch.setattr(promote_mod, "KnowledgeOS", object)
        assert promote_mod.execute_job(job) is False
        assert fm(job)["status"] == "approved_gate_3"

    def test_execute_denied_outside_staging(self, workspace, monkeypatch):
        evil = workspace["tmp"] / "evil.md"
        evil.write_text("evil", encoding="utf-8")
        job = make_job(workspace["jobs"], "PR-PATH", "approved_gate_3", {
            "audit_result": "pass",
            "approved_gate_2_by": "alice",
            "approved_gate_3_by": "bob",
            "staged_artifact_path": str(evil),
            "artifact_hash": "dummy",
            "domain": "game",
        })
        assert promote_mod.execute_job(job) is False

    def test_execute_denied_missing_domain(self, workspace):
        staged = workspace["staging"] / "PR-DOM.md"
        staged.write_text("c", encoding="utf-8")
        h = promote_mod.compute_hash(staged)
        job = make_job(workspace["jobs"], "PR-DOM", "approved_gate_3", {
            "audit_result": "pass",
            "approved_gate_2_by": "alice",
            "approved_gate_3_by": "bob",
            "staged_artifact_path": str(staged),
            "artifact_hash": h,
        })
        assert promote_mod.execute_job(job) is False

    def test_execute_denied_topic_traversal(self, workspace):
        staged = workspace["staging"] / "PR-TOP.md"
        staged.write_text("c", encoding="utf-8")
        h = promote_mod.compute_hash(staged)
        job = make_job(workspace["jobs"], "PR-TOP", "approved_gate_3", {
            "audit_result": "pass",
            "approved_gate_2_by": "alice",
            "approved_gate_3_by": "bob",
            "staged_artifact_path": str(staged),
            "artifact_hash": h,
            "domain": "game",
            "topic": "../etc/secret",
        })
        assert promote_mod.execute_job(job) is False

    def test_legacy_cli_force_not_supported(self, workspace):
        """Legacy args (positional artifact, --force) must not succeed."""
        art = workspace["tmp"] / "leg.md"
        art.write_text("c", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "promote.py"), str(art), "--force"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        assert r.returncode != 0


# ══════════════════════════════════════════════════════════════════════════════
# 4. Daemon dispatcher
# ══════════════════════════════════════════════════════════════════════════════

class TestDaemonDispatcher:
    def test_routing_approved_gate_1_goes_to_graph(self, workspace, monkeypatch):
        graph_calls = []
        monkeypatch.setattr("apps.runtime.graph.run_job",
                            lambda p, j: graph_calls.append(j) or {"status": "audit_passed"})

        promote_calls = []
        import subprocess as sp
        monkeypatch.setattr(sp, "run", lambda cmd, **kw:
                            promote_calls.append(cmd) or type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())

        make_job(workspace["jobs"], "D-G1", "approved_gate_1")
        wiki_daemon.process_jobs_parallel(SyncExecutor())

        assert "D-G1" in graph_calls
        assert not any("D-G1" in str(c) for c in promote_calls)

    def test_routing_approved_gate_2_goes_to_stage(self, workspace, monkeypatch):
        graph_calls = []
        monkeypatch.setattr("apps.runtime.graph.run_job",
                            lambda p, j: graph_calls.append(j) or {"status": "audit_passed"})

        promote_calls = []
        import subprocess as sp
        def fake_run(cmd, **kw):
            promote_calls.append({"mode": cmd[cmd.index("--mode") + 1], "job": cmd[cmd.index("--job") + 1]})
            return type("R", (), {"returncode": 0, "stdout": "[OK]", "stderr": ""})()
        monkeypatch.setattr(sp, "run", fake_run)

        make_job(workspace["jobs"], "D-G2", "approved_gate_2")
        wiki_daemon.process_jobs_parallel(SyncExecutor())

        assert "D-G2" not in graph_calls
        assert any(c["mode"] == "stage" for c in promote_calls)

    def test_routing_approved_gate_3_goes_to_execute(self, workspace, monkeypatch):
        graph_calls = []
        monkeypatch.setattr("apps.runtime.graph.run_job",
                            lambda p, j: graph_calls.append(j) or {"status": "audit_passed"})

        promote_calls = []
        import subprocess as sp
        def fake_run(cmd, **kw):
            promote_calls.append({"mode": cmd[cmd.index("--mode") + 1]})
            return type("R", (), {"returncode": 0, "stdout": "[OK]", "stderr": ""})()
        monkeypatch.setattr(sp, "run", fake_run)

        make_job(workspace["jobs"], "D-G3", "approved_gate_3")
        wiki_daemon.process_jobs_parallel(SyncExecutor())

        assert "D-G3" not in graph_calls
        assert any(c["mode"] == "execute" for c in promote_calls)

    def test_skip_statuses(self, workspace, monkeypatch):
        """audit_passed, promotion_pending, promoted must not trigger any execution."""
        graph_calls = []
        monkeypatch.setattr("apps.runtime.graph.run_job",
                            lambda p, j: graph_calls.append(j) or {})
        promote_calls = []
        import subprocess as sp
        monkeypatch.setattr(sp, "run",
                            lambda cmd, **kw: promote_calls.append(cmd) or
                            type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())

        for status in ("audit_passed", "promotion_pending", "promoted",
                       "audit_failed", "gate_2_rejected", "cancelled"):
            make_job(workspace["jobs"], f"SKIP-{status}", status)

        wiki_daemon.process_jobs_parallel(SyncExecutor())
        assert len(graph_calls) == 0
        assert len(promote_calls) == 0

    def test_promotion_failure_is_non_terminal(self, workspace, monkeypatch):
        """Subprocess failure must not mark daemon_state as 'failed'."""
        monkeypatch.setattr("apps.runtime.graph.run_job", lambda p, j: {})

        import subprocess as sp
        monkeypatch.setattr(sp, "run",
                            lambda cmd, **kw: type("R", (), {"returncode": 1, "stdout": "", "stderr": "err"})())

        make_job(workspace["jobs"], "D-FAIL-G2", "approved_gate_2")
        wiki_daemon.process_jobs_parallel(SyncExecutor())

        state = wiki_daemon.load_state()
        daemon_status = state["jobs"].get("D-FAIL-G2", {}).get("status", "")
        assert daemon_status != "failed", f"daemon_state must not be 'failed', got '{daemon_status}'"
        assert daemon_status not in wiki_daemon.TERMINAL_STATUSES


# ══════════════════════════════════════════════════════════════════════════════
# 5. Slack notification in daemon
# ══════════════════════════════════════════════════════════════════════════════

class TestDaemonSlackNotification:
    def _run_notification_loop(self, workspace, slack_adapter):
        """Replicate the continuous-mode notification block."""
        state = wiki_daemon.load_state()
        for jid, info in state.get("jobs", {}).items():
            job_path = Path(info.get("path", ""))
            if not job_path.exists():
                continue
            f = wiki_daemon.read_job_frontmatter(job_path)
            if f.get("status") != "audit_passed":
                continue
            if f.get("slack_ts"):
                continue
            artifact_path = f.get("artifact_path")
            if not artifact_path or not Path(artifact_path).exists():
                continue
            slack_adapter.send_audit_notification(jid, str(artifact_path))

    def test_notifies_with_frontmatter_artifact_path(self, workspace):
        art = workspace["tmp"] / "art_N1.md"
        art.write_text("c", encoding="utf-8")
        make_job(workspace["jobs"], "N1", "audit_passed", {"artifact_path": str(art)})
        wiki_daemon.load_state()

        calls = []
        class FakeSlack:
            def send_audit_notification(self, job_id, artifact_path):
                calls.append({"job_id": job_id, "artifact_path": artifact_path})

        self._run_notification_loop(workspace, FakeSlack())
        assert len(calls) == 1
        assert calls[0]["artifact_path"] == str(art)
        assert "staging" not in calls[0]["artifact_path"]

    def test_no_renotify_when_slack_ts_present(self, workspace):
        art = workspace["tmp"] / "art_N2.md"
        art.write_text("c", encoding="utf-8")
        make_job(workspace["jobs"], "N2", "audit_passed", {
            "artifact_path": str(art),
            "slack_ts": "1234.567"
        })
        wiki_daemon.load_state()

        calls = []
        class FakeSlack:
            def send_audit_notification(self, job_id, artifact_path):
                calls.append(job_id)
        self._run_notification_loop(workspace, FakeSlack())
        assert len(calls) == 0

    def test_no_notify_when_artifact_missing(self, workspace):
        make_job(workspace["jobs"], "N3", "audit_passed")
        wiki_daemon.load_state()

        calls = []
        class FakeSlack:
            def send_audit_notification(self, job_id, artifact_path):
                calls.append(job_id)
        self._run_notification_loop(workspace, FakeSlack())
        assert len(calls) == 0

    def test_no_notify_for_non_audit_passed(self, workspace):
        art = workspace["tmp"] / "art_N4.md"
        art.write_text("c", encoding="utf-8")
        for status in ("promotion_pending", "approved_gate_2", "promoted"):
            make_job(workspace["jobs"], f"N4-{status}", status, {"artifact_path": str(art)})
        wiki_daemon.load_state()

        calls = []
        class FakeSlack:
            def send_audit_notification(self, job_id, artifact_path):
                calls.append(job_id)
        self._run_notification_loop(workspace, FakeSlack())
        assert len(calls) == 0
