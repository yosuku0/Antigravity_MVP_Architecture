# Verification Plan
## NIM-Kinetic Meta-Agent MVP
## Version: 1.0
## Date: 2026-04-24
## Focus: Failure Modes, Not Happy Path

---

## Philosophy

This plan does not verify that the system "works." It verifies that the system **fails safely** when things go wrong. Every test must have a clear pass/fail signal observable by an automated script or a human operator with a single command.

**Contract = Test Monolith (CTM):** No implementation task is complete until its corresponding verification test passes.

---

## Test Inventory

### T001: Duplicate Claim Prevention

| Field | Value |
|---|---|
| **Purpose** | Ensure two concurrent daemons (or a daemon and a manual script) cannot claim the same job. |
| **Setup** | Create `JOB-001.md` with `status: approved_gate_1`. Start two `wiki_daemon.py` instances (Process A and Process B) pointing at the same `work/jobs/` directory. |
| **Trigger** | Both processes detect `JOB-001` simultaneously. |
| **Expected Outcome** | Exactly one process acquires `work/locks/JOB-001.lock`. The other logs `claim_rejected: already_locked` and proceeds to the next job (or sleeps). `JOB-001` status remains `claimed` (not corrupted to `executing` by the loser). |
| **Pass/Fail Signal** | `PASS`: Only one lock file exists; its content matches the winning PID. `FAIL`: Two lock files exist, or JOB status is corrupted, or both processes report success. |
| **Automatable** | **Now** — Python `pytest` with `multiprocessing`. |
| **CTM Task** | TASK-003 (daemon implementation) |

---

### T002: Recovery from Corrupted `daemon_state.json`

| Field | Value |
|---|---|
| **Purpose** | Verify that `daemon_state.json` corruption does not lose job state or allow double-execution. |
| **Setup** | Create 3 jobs in various states (`approved_gate_1`, `executing`, `audit_passed`). Corrupt `daemon_state.json` by writing invalid JSON (`{ "jobs": [ broken`). Stop daemon. |
| **Trigger** | Restart daemon. |
| **Expected Outcome** | Daemon detects corruption, logs `daemon_state_rebuild_initiated`, rebuilds state from `work/jobs/` + `work/locks/` + `logs/daemon.jsonl`. All 3 jobs are in correct states post-rebuild. No job is lost or duplicated. |
| **Pass/Fail Signal** | `PASS`: Daemon starts without crash; rebuilt state matches ground truth (diff against independent scan). `FAIL`: Daemon crashes on startup, or jobs are missing, or states are wrong. |
| **Automatable** | **Now** — shell script that corrupts file and asserts via Python. |
| **CTM Task** | TASK-003 (daemon implementation) |

---

### T003: Stale Lock Reclaim Behavior

| Field | Value |
|---|---|
| **Purpose** | Verify that a daemon crash during execution does not orphan a job forever. |
| **Setup** | Create `JOB-002.md` with `status: approved_gate_1`. Start daemon; let it claim the job (creates lock). Kill daemon with `SIGKILL` (simulates crash). Wait 11 minutes. |
| **Trigger** | Restart daemon after 11 minutes. |
| **Expected Outcome** | Daemon detects `work/locks/JOB-002.lock` with mtime > 10 min, but no active process. Moves lock to `work/locks/archived/`. Transitions `JOB-002` to `failed` with `reason: stale_lock_recovered`. Logs the recovery action. |
| **Pass/Fail Signal** | `PASS`: Lock archived; JOB status is `failed`; log entry exists. `FAIL`: Lock remains in place; JOB status stuck; no recovery. |
| **Automatable** | **Now** — shell script with `sleep` (or mock clock). |
| **CTM Task** | TASK-003 (daemon implementation) |

---

### T004: Router Fallback Activation

| Field | Value |
|---|---|
| **Purpose** | Verify that `llm_router.py` switches to fallback provider when NIM times out or returns 5xx. |
| **Setup** | Configure `routing_config.yaml` with `nim_fast` primary and `classify_local` fallback. Set `NVIDIA_API_KEY` to an invalid key (or block `integrate.api.nvidia.com` via `hosts` file redirect to `127.0.0.1:9999`). Ensure Ollama is running. |
| **Trigger** | Call `llm_router.get_client("nim_fast").chat(...)` with timeout=5s. |
| **Expected Outcome** | Primary call fails (timeout or auth error). Router attempts fallback `classify_local` (Ollama). Returns response from Ollama. Logs `fallback_activated: classify_local` to `model_calls.jsonl`. |
| **Pass/Fail Signal** | `PASS`: Response returned; JSONL log contains `fallback_activated: true`. `FAIL`: Exception propagates to caller with no fallback attempt, or fallback loops infinitely. |
| **Automatable** | **Now** — Python test with mock server or invalid key. |
| **CTM Task** | TASK-004 (llm_router patch + Kimi) |

---

### T005: Explicit Failure When Provider Credentials Are Missing

| Field | Value |
|---|---|
| **Purpose** | Verify that the system fails fast and loudly when API keys are missing — never silently degrades or uses default/demo keys. |
| **Setup** | Unset `NVIDIA_API_KEY` and `NIM_API_KEY`. Ensure no `.env` file is loaded. |
| **Trigger** | Call `NIMClient.from_config("nim_fast")` or `llm_router.get_client("nim_fast")`. |
| **Expected Outcome** | Immediate `EnvironmentError` with message: `"NVIDIA_API_KEY not set. Obtain at https://build.nvidia.com → Get API Key"`. No network request is attempted. No fallback to "free tier default key." |
| **Pass/Fail Signal** | `PASS`: `EnvironmentError` raised within 100ms; message contains URL. `FAIL`: Slow timeout (implies network attempt), or fallback to demo key, or silent None return. |
| **Automatable** | **Now** — Python `pytest` with `monkeypatch.delenv`. |
| **CTM Task** | TASK-004 (llm_router patch + Kimi) |

---

### T006: Audit FAIL Prevents Wiki Promotion

| Field | Value |
|---|---|
| **Purpose** | Verify that `audit.py` FAIL result blocks `promote.py` regardless of human intent. |
| **Setup** | Create a completed job artifact containing a fake secret pattern (`AWS_SECRET_ACCESS_KEY=AKIA...`). Set JOB status to `audit_failed`. |
| **Trigger** | Run `scripts/promote.py --job work/jobs/JOB-003.md --mode execute`. |
| **Expected Outcome** | `promote.py` checks `audit_result` and Gate 2/3 approval fields. If `audit_result != "pass"`, exits with code `1` and message `"Promotion blocked: audit_result=fail. Fix audit issues before promotion."`. No write to `wiki/`. |
| **Pass/Fail Signal** | `PASS`: Exit code 1; `wiki/` unchanged; log entry `promotion_blocked: audit_fail`. `FAIL`: `wiki/` receives new file; or exit code 0. |
| **Automatable** | **Now** — shell script with temp directories. |
| **CTM Task** | TASK-007 (audit + promote) |

---

### T007: Gate 1 Not Approved → Execution Blocked

| Field | Value |
|---|---|
| **Purpose** | Verify that a job in `CREATED` state cannot enter `EXECUTING` without human approval. |
| **Setup** | Create `JOB-004.md` with `status: created`. Start LangGraph graph directly (bypassing daemon) with this job. |
| **Trigger** | LangGraph `entry_node` processes JOB-004. |
| **Expected Outcome** | `entry_node` reads `status`. If `status != "approved_gate_1"`, transitions to terminal state and raises `NodeInterrupt` (or equivalent) with message `"Gate 1 not approved. JOB blocked."`. No execution occurs. |
| **Pass/Fail Signal** | `PASS`: Interrupt raised; no artifacts created; checkpoint shows blocked state. `FAIL`: Execution proceeds; artifacts appear. |
| **Automatable** | **Now** — Python test invoking graph with mock state. |
| **CTM Task** | TASK-005 (LangGraph graph + HITL) |

---

### T008: Gate 2 Not Approved → No Artifact Reflection

| Field | Value |
|---|---|
| **Purpose** | Verify that audit-passed artifacts are not merged or promoted without Gate 2 approval. |
| **Setup** | Create `JOB-005.md` with `status: audit_passed` but no `approved_gate_2_by` field. Place a valid artifact in `memory/working/JOB-005/`. |
| **Trigger** | Run `scripts/promote.py --job work/jobs/JOB-005.md --mode stage` or attempt to merge artifact. |
| **Expected Outcome** | Any tool that would apply the artifact (merge script, promote script) checks `approved_gate_2_by`. If missing, exits with code `1` and message `"Gate 2 approval required. Run: approve --job JOB-005 --gate 2"`. Artifact remains in `memory/working/`; never reaches `wiki/` or git branch. |
| **Pass/Fail Signal** | `PASS`: Artifact not promoted; git branch unchanged. `FAIL`: Artifact merged or promoted without approval field. |
| **Automatable** | **Now** — shell script with temp git repo and temp wiki dir. |
| **CTM Task** | TASK-005 (LangGraph graph + HITL) |

---

### T009: Gate 3 Not Approved → No Wiki Promotion

| Field | Value |
|---|---|
| **Purpose** | Verify that `wiki/` is never written before Gate 3 approval. |
| **Setup** | Create `JOB-006.md` with `status: approved_gate_2` and staging area populated, but no `approved_gate_3_by`. |
| **Trigger** | Run `scripts/promote.py --job work/jobs/JOB-006.md --mode execute` without required Gate 3 metadata in frontmatter. |
| **Expected Outcome** | `promote.py` checks `approved_gate_3_by` and `approved_gate_3_at` in the JOB frontmatter. If missing, exits code 1 with message `"Gate 3 approval required for wiki write."`. `wiki/` directory listing unchanged. |
| **Pass/Fail Signal** | `PASS`: `wiki/` unchanged; exit code 1. `FAIL`: New file in `wiki/`; exit code 0. |
| **Automatable** | **Now** — shell script with temp wiki directory. |
| **CTM Task** | TASK-007 (audit + promote) |

---

### T010: [REMOVED — Qdrant is Deferred to P1]

This test is **not in the MVP release gate.** Qdrant and RAG are deferred per `mvp_scope_freeze.md`. There is no `rag_retrieve_node` in MVP, so there is nothing to test. A P1 equivalent test will be added when Qdrant is integrated.

---

### T011: CLI-Only Operation (No External Service Dependencies)

| Field | Value |
|---|---|
| **Purpose** | Verify that the core loop runs with zero external service dependencies. CLI is the only MVP ingress; Slack is deferred. The system must not attempt Slack connections, webhooks, or Bolt initialization. |
| **Setup** | Ensure no Slack environment variables are set. No `.env` file loaded. No Slack-related packages imported. |
| **Trigger** | Run CLI command: `./agent "Create a test job for T011"`. |
| **Expected Outcome** | JOB-007.md is created. Daemon detects it. Full loop executes through NIM router, audit, HITL (CLI prompts), promote. No network calls to any messaging service attempted. Completion notification is a console log line: `[T011] JOB complete: JOB-007`. |
| **Pass/Fail Signal** | `PASS`: End-to-end completion with exit code 0; no import of `slack_bolt`, `slack_sdk`, or similar; no network connection to `slack.com`. `FAIL`: Import error for Slack SDK; unexpected network call; job blocked waiting for external service. |
| **Automatable** | **Now** — shell script with `unshare -n` (network namespace) or import audit. |
| **CTM Task** | TASK-002 (CLI gateway + job generator) |

---

### T012: Hermes Memory Not Treated as Source of Truth

| Field | Value |
|---|---|
| **Purpose** | Verify that Hermes memory (`runtime/hermes/memory.md`) is never read as canonical knowledge during research or execution. |
| **Setup** | Place a deliberately false statement in `runtime/hermes/memory.md`: `"Python 4.0 was released in 2025."`. Place the true statement in `wiki/python.md`: `"Python 3.13 is the latest stable release as of 2025."`. Create a job asking: "What is the latest stable Python release?" |
| **Trigger** | Execute job through research node. |
| **Expected Outcome** | Research node loads `wiki/python.md` (and other `wiki/` files) into context. It does NOT load `runtime/hermes/memory.md`. The answer reflects `wiki/` content (Python 3.13). `audit.py` scans loaded sources and verifies no `runtime/hermes/` paths appear in `evidence.sources`. |
| **Pass/Fail Signal** | `PASS`: Answer cites `wiki/python.md`; no `runtime/hermes/` in evidence sources. `FAIL`: Answer cites Hermes memory; or Hermes path appears in evidence. |
| **Automatable** | **Now** — Python test with mock filesystem and fixed prompts. |
| **CTM Task** | TASK-007 (audit + promote) |

---

### T013: Provider-Switch Retry Budget Exhaustion

| Field | Value |
|---|---|
| **Purpose** | Verify that after 2 provider switches, the job fails fast instead of looping through all providers. |
| **Setup** | Configure `routing_config.yaml` with fallback chain: `nim_fast → classify_local`. Block both NIM and Ollama (stop Ollama service; block NIM via hosts file). |
| **Trigger** | Execute a job requiring `moderate` complexity (routes to `nim_fast`). |
| **Expected Outcome** | Router tries `nim_fast` (fails). Switches to `classify_local` (fails). Budget exhausted (2 switches). Job transitions to `FAILED` with `failure_reason: provider_budget_exhausted`. No attempt to use paid providers (Claude/Gemini) as emergency fallback. |
| **Pass/Fail Signal** | `PASS`: Exactly 2 provider calls attempted in `model_calls.jsonl`; job status FAILED; no additional provider calls. `FAIL`: More than 2 provider calls; job hangs; or emergency fallback to paid provider. |
| **Automatable** | **Now** — Python test with mock providers that always raise `ConnectionError`. |
| **CTM Task** | TASK-004 (llm_router patch + Kimi) |

---

### T014: Daemon Restart Mid-Execution (MVP: Safe Fail, P1: Resume)

| Field | Value |
|---|---|
| **Purpose** | **MVP scope:** Verify that daemon crash during execution does not orphan the job or create duplicate claims. The job must fail safely, not hang. **P1 scope (documented, not tested):** Resume from LangGraph checkpoint. |
| **Setup** | Create `JOB-008.md` with `status: approved_gate_1`. Start daemon. Let daemon claim and transition to `EXECUTING`. Kill daemon with `SIGKILL` during execution. |
| **Trigger** | Restart daemon after 5 seconds. |
| **Expected Outcome (MVP)** | Daemon rebuilds state from `work/jobs/` + `work/locks/` + `logs/daemon.jsonl`. Detects `JOB-008` as `executing`. If checkpoint exists: transitions to `FAILED` with `reason: checkpoint_resume_deferred`. If no checkpoint: transitions to `FAILED` with `reason: no_checkpoint`. Lock is archived. JOB status is terminal `FAILED`. No duplicate artifacts. Operator may clone to new JOB. |
| **Pass/Fail Signal** | `PASS`: JOB-008 status is `FAILED` with explicit reason; no duplicate files; lock archived. `FAIL`: Job stuck in `EXECUTING`; duplicate artifacts; daemon crashes on restart. |
| **Automatable** | **Manual for MVP release gate** — requires process timing control. Automated test targeted for P1 when checkpoint resume is implemented. |
| **CTM Task** | TASK-003 (daemon implementation) |

---

### T015: Idempotent Re-Run of Previously Failed Job

| Field | Value |
|---|---|
| **Purpose** | Verify that a failed job can be cloned and re-run without side effects from the previous attempt. |
| **Setup** | Create `JOB-009.md`. Let it fail during execution (e.g., invalid routing context). Transition to `FAILED`. Clone to `JOB-010.md` with same objective but new ID. |
| **Trigger** | Submit `JOB-010.md` for execution. |
| **Expected Outcome** | `JOB-010` executes independently. No reference to `JOB-009` artifacts. `memory/working/JOB-009/` is not read. `model_calls.jsonl` tracks `JOB-010` separately. `JOB-009` state remains `FAILED` and untouched. |
| **Pass/Fail Signal** | `PASS`: JOB-010 completes (or fails independently); JOB-009 unchanged; no cross-job contamination in logs or filesystem. `FAIL`: JOB-010 loads JOB-009 artifacts; JOB-009 status modified; shared mutable state detected. |
| **Automatable** | **Now** — Python test with temp directories and controlled failure injection. |
| **CTM Task** | TASK-005 (LangGraph graph + HITL) |

---

### T016: Audit FAIL and Gate 2 Rejection Are Distinguishable

| Field | Value |
|---|---|
| **Purpose** | Verify that automated audit failure (`AUDIT_FAILED`) and human rejection at Gate 2 (`GATE_2_REJECTED`) are recorded as separate states, separate log entries, and separate metrics. They must never be conflated. |
| **Setup** | Create two jobs: `JOB-011` with a secret pattern in its artifact (triggers `audit.py` FAIL); `JOB-012` with a clean artifact that a human operator will reject at Gate 2. |
| **Trigger** | Run both jobs through the full loop. For `JOB-011`, let `audit.py` run. For `JOB-012`, approve Gate 1, let it execute and audit pass, then explicitly reject at Gate 2. |
| **Expected Outcome** | `JOB-011` status: `AUDIT_FAILED`. `audit_result: fail` in JOB file. Log entry: `event: audit_failed, reason: secret_detected`. `JOB-012` status: `GATE_2_REJECTED`. `audit_result: pass` in JOB file. `gate_2_rejected_by: human` in JOB file. Log entry: `event: gate_2_rejected, reason: human_rejection`. Metrics counter `audit_failed_total` and `gate_2_rejected_total` are separate. |
| **Pass/Fail Signal** | `PASS`: Two distinct terminal states; two distinct log event types; JOB-11 has `audit_result=fail`, JOB-12 has `audit_result=pass` + `gate_2_rejected_by`. `FAIL`: Both jobs end in same state; log events conflated; metrics merged. |
| **Automatable** | **Now** — Python test with mock human rejection injection. |
| **CTM Task** | TASK-007 (audit + promote) |

---

## Test Execution Matrix

| Test | Automatable Now | Automatable Later | Manual Only | CTM Task | Risk if Fails |
|---|---|---|---|---|---|
| T001 | ✅ | | | TASK-003 | Double execution, data corruption |
| T002 | ✅ | | | TASK-003 | Lost jobs, double execution |
| T003 | ✅ | | | TASK-003 | Orphaned jobs, resource leak |
| T004 | ✅ | | | TASK-004 | No NIM usage, all tasks fallback unnecessarily |
| T005 | ✅ | | | TASK-004 | Silent credential leaks, slow failures |
| T006 | ✅ | | | TASK-007 | Secret promotion to wiki, security breach |
| T007 | ✅ | | | TASK-005 | Runaway execution, unapproved changes |
| T008 | ✅ | | | TASK-005 | Bad artifacts merged without review |
| T009 | ✅ | | | TASK-007 | Wiki pollution, unapproved knowledge |
| T010 | — | — | — | — | [Deferred to P1 — Qdrant not in MVP] |
| T011 | ✅ | | | TASK-002 | External service dependency blocks core loop |
| T012 | ✅ | | | TASK-007 | Factual drift, tactical memory treated as truth |
| T013 | ✅ | | | TASK-004 | Infinite fallback loops, cost explosion |
| T014 | | | ✅ | TASK-003 | Lost work, duplicate artifacts |
| T015 | ✅ | | | TASK-005 | Cross-job contamination, debugging hell |
| T016 | ✅ | | | TASK-007 | Cannot distinguish automated failure from human rejection |

---

## Minimum Release Gate

The MVP is **not releasable** until:

1. **All MVP-scope automated tests (T001–T009, T011–T013, T015–T016) have passing automation.** T010 is excluded (Qdrant deferred). T014 is manual.
2. **T014 has a documented manual verification procedure** with operator checklist. The procedure must verify safe fail (not hang, not duplicate) after daemon restart.
3. **Zero tests in the "Risk if Fails = Security Breach" category (T006, T007, T008, T009, T012, T016) are failing.**
4. **Any failing test in category 3 triggers a scope freeze hold** — no new features until the test passes.

---

## Test Automation Infrastructure

```
tests/
  conftest.py              # Shared fixtures: temp dirs, mock providers
  test_daemon.py           # T001, T002, T003, T014 (manual)
  test_router.py           # T004, T005, T013
  test_hitl.py             # T007, T008, T009, T015, T016
  test_audit_promote.py    # T006, T012
  test_ingress.py          # T011
```

**Note:** `test_degraded.py` (originally T010 + T011) is removed. T010 is deferred to P1. T011 moves to `test_ingress.py`.

Each test file must:
- Use `pytest` fixtures for temp filesystems.
- Mock external APIs (NIM, Ollama) using `responses` or `unittest.mock`. No Slack mocking — Slack is not in MVP.
- Leave no persistent state (all files under `tmp_path`).
- Run in < 30 seconds individually.

---

*Plan version: 1.0*
*Next revision: After CTM Task completion or upon new failure mode discovery.*
