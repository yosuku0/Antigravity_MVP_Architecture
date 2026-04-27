# Phase 2 Work Breakdown Structure
## NIM-Kinetic Meta-Agent MVP
## Date: 2026-04-24
## Frozen Artifact Set: mvp_scope_freeze.md, job_lifecycle_spec.md, verification_plan.md, ADR-001-mvp-control-plane.md

---

## 1. WBS Strategy

Build order follows the principle of **verify before build, foundation before feature, safety before speed.** The first block is pure discovery — find what exists in the repo, confirm what runs, and identify what must be built from scratch. Only after discovery completes do we begin implementation. Runtime and orchestration (Block B) come before router integration (Block C) because the router needs a graph to plug into. Audit/promote (Block D) come after execution works because there is nothing to audit until jobs execute. Verification automation (Block E) runs in parallel with Blocks B-D but depends on each block's outputs. Release readiness (Block F) is the final gate. This order minimizes the risk of discovering a missing foundational component after downstream work is already committed.

---

## 2. Execution Blocks

### Block A: Repo Verification / Discovery
**Goal:** Establish the ground truth of what exists, what runs, and what is missing.
**Exit Condition:** Every file in the "Document-Verified but Not Code-Verified" inventory has been located or confirmed missing. A decision record exists for each missing file (build vs. adapt). The `NVIDIA_API_KEY` status is known.

### Block B: Runtime & Orchestration
**Goal:** Implement the minimal LangGraph StateGraph and wiki_daemon that can load a job, apply a Gate 1 interrupt, route it, and execute it.
**Exit Condition:** A job can be submitted via CLI, detected by the daemon, claimed, routed, and executed through a LangGraph node chain. HITL Gate 1 blocks execution until approved.

### Block C: Router Integration
**Goal:** Wire NIM router, complexity_scorer, Kimi provider, and Ollama fallback into the execution path.
**Exit Condition:** `router_node` calls `complexity_scorer.classify_job_file()` and dispatches to the correct provider (NIM, Ollama, or paid). Fallback activates on timeout/5xx. Provider-switch budget is enforced.

### Block D: Audit / Promote / Knowledge Integrity
**Goal:** Implement audit gate, promote script, Hermes reflection, and knowledge boundary enforcement.
**Exit Condition:** `audit.py` returns WARN/FAIL and blocks promotion. `promote.py` writes to `wiki/` only in `PROMOTED` state with Gate 3 approval. `GATE_2_REJECTED` is distinct from `AUDIT_FAILED`. Hermes never becomes canonical.

### Block E: Verification Automation
**Goal:** Build the test suite that proves the system fails safely.
**Exit Condition:** All 13 MVP-scope automated tests (T001–T009, T011–T013, T015–T016) pass. T014 manual procedure is documented.

### Block F: Release Readiness
**Goal:** Complete the MVP release gate.
**Exit Condition:** All release criteria from `verification_plan.md` §Minimum Release Gate are satisfied.

---

## 3. Task Table

### BLOCK A: Repo Verification / Discovery

| ID | Title | Purpose | Inputs | Outputs | Depends On | Acceptance Criteria | Related Tests | Risk if Skipped |
|---|---|---|---|---|---|---|---|---|
| A-001 | Verify `graph.py` existence | Determine if LangGraph StateGraph exists or must be built from scratch. | Kinetic_Protocol repo | Discovery report: file path, import status, skeleton vs. complete | — | `find` returns path; `python -c "import graph"` succeeds or fails with clear error | — | If skipped and file is missing, all Block B estimates are wrong |
| A-002 | Verify `wiki_daemon.py` existence | Determine if daemon exists or must be built from scratch. | All 5 project repos | Discovery report: file path, functionality level, watchdog usage | — | `find` across all repos; file content inspected | — | **P0 risk** — if skipped and file is missing, Block B scope explodes |
| A-003 | Verify `audit.py` existence | Determine if audit gate exists or must be built. | All project repos | Discovery report: file path, WARN/FAIL logic, secret scan capability | — | `find` returns path; script can be invoked with `--help` or is identified as missing | — | If skipped, Block D scope is undefined |
| A-004 | Verify `promote.py` existence | Determine if promotion script exists or must be built. | All project repos | Discovery report: file path, Gate 3 enforcement, wiki write logic | — | `find` returns path; `--mode stage` and `--mode execute` parameters detected | — | If skipped, Block D scope is undefined |
| A-005 | Verify `hermes_reflect.py` existence | Determine if Hermes reflection exists or must be built. | All project repos | Discovery report: file path, append-only behavior | — | `find` returns path; file content inspected | — | Low risk — simple append if missing |
| A-006 | Verify NIM patch on `llm_router.py` | Confirm 4-line NIM integration patch is applied. | `Kinetic_Protocol/apps/crewai_crews/llm_router.py` | Patch status report: applied / not applied / partially applied | — | `grep NIMClient` in file; grep results documented | — | **P0 risk** — if not applied, router tasks are larger than estimated |
| A-007 | Execute `complexity_scorer.py` | Verify scorer runs end-to-end with local Ollama. | `complexity_scorer.py`, running Ollama | Execution report: success/failure, latency, output format | — | `python complexity_scorer.py "test task"` produces valid JSON with `level` and `recommended_context` fields | — | **P0 risk** — if broken, router_node cannot classify |
| A-008 | Verify real NIM connectivity | Confirm NIM API key works and returns a response. | `NVIDIA_API_KEY` or `NIM_API_KEY`, `nim_router.py` | Connectivity report: success/failure, model tested, latency | A-006 | `python nim_router.py` produces a response within 30s | — | **P0 risk** — if key is invalid, all NIM tests fail |
| A-009 | Verify Ollama runtime and models | Confirm Ollama is running with required models. | WSL2 environment | Model availability report: `qwen2.5:7b`, `qwen2.5-coder:7b`, `gemma2:27b` | — | `ollama list` shows models; `ollama ps` shows service running | T004 | **P0 risk** — Ollama is the fallback safety net |
| A-010 | Record discovery decisions | Document build-vs-adapt decisions for all unverified files. | A-001 through A-009 reports | Decision log: `docs/discovery_report_A.md` | A-001..A-009 | Every unverified item has a decision: BUILD / ADAPT / DEPRECATE | — | If skipped, implementation proceeds on false assumptions |

### BLOCK B: Runtime & Orchestration

| ID | Title | Purpose | Inputs | Outputs | Depends On | Acceptance Criteria | Related Tests | Risk if Skipped |
|---|---|---|---|---|---|---|---|---|
| B-001 | Create `apps/daemon/wiki_daemon.py` (or adapt existing) | Minimal watchdog daemon: detects pending jobs, claims with atomic lock, transitions status, writes `daemon.jsonl`. | Discovery report A-002, `job_lifecycle_spec.md` §2-§4 | `apps/daemon/wiki_daemon.py`; `logs/daemon.jsonl` | A-002, A-010 | Daemon starts; detects `status: approved_gate_1` job; creates atomic lock; transitions to `claimed`; writes jsonl event | T001, T002, T003 | No job execution without daemon |
| B-002 | Implement `daemon_state.json` rebuild | Daemon rebuilds state from `work/jobs/` + `work/locks/` + `logs/daemon.jsonl` on restart. Never trusts stale cache. | B-001 | State rebuild logic in daemon | B-001 | Corrupt `daemon_state.json`; restart daemon; state rebuilt correctly with 0 jobs lost | T002 | Daemon restart loses jobs |
| B-003 | Implement stale-lock reclaim | Locks > 10 min old with no active process are archived; job fails or returns to `approved_gate_1`. | B-001, `job_lifecycle_spec.md` §4 | Stale-lock recovery logic | B-001 | Create lock; simulate crash; wait 11 min; restart; lock archived; job status correct | T003 | Orphaned jobs after crash |
| B-004 | Create `apps/runtime/graph.py` (or adapt existing) | LangGraph StateGraph with nodes: `load_job` → `router_node` → `crew_execute_node` → `audit_node`. Edges defined per lifecycle spec. | Discovery report A-001, ADR-001, `job_lifecycle_spec.md` | `apps/runtime/graph.py` with StateGraph definition | A-001, A-010 | Graph compiles; `graph.invoke(initial_state)` runs without crash; state transitions follow valid transitions diagram | — | No orchestration without graph |
| B-005 | Implement HITL Gate 1 (`interrupt_before execute`) | LangGraph interrupt prevents execution until human approves via CLI. | B-004, `job_lifecycle_spec.md` §6 | Gate 1 enforcement in graph | B-004 | Submit unapproved job; graph interrupts before execute; approve via CLI; graph resumes | T007 | Runaway execution |
| B-006 | Implement `crew_execute_node` | Single CrewAI crew execution node. Static roles from YAML config. No dynamic crew creation. Reports success/failure/artifact to LangGraph state. | B-004, ADR-001 §3 | `crew_execute_node` in graph or separate module | B-004 | Crew executes plan; artifact written to `memory/working/JOB-###/`; status in state reflects result | — | No execution capability |
| B-007 | Implement `audit_node` in graph | Calls `audit.py` (lightweight regex + file checks). Transitions to `AUDIT_PASSED` or `AUDIT_FAILED` based on result. | B-004, D-001 (audit.py must exist/work) | `audit_node` in graph | B-004, D-001 | Audit runs after execution; PASS → wait for Gate 2; FAIL → terminal until rework | T006 | Bad artifacts advance unchecked |
| B-008 | Implement HITL Gate 2 (artifact approval) | After `AUDIT_PASSED`, graph waits for human approval/rejection via CLI. Approval → `APPROVED_GATE_2`. Rejection → `GATE_2_REJECTED`. | B-007, `job_lifecycle_spec.md` §6, §C2 | Gate 2 enforcement; `GATE_2_REJECTED` state handling | B-007 | Audit passes; graph interrupts; human approves → `APPROVED_GATE_2`; human rejects → `GATE_2_REJECTED` | T008, T016 | Cannot distinguish human rejection from audit failure |
| B-009 | Implement `PROMOTION_PENDING` → `APPROVED_GATE_3` → `PROMOTED` chain | `promote.py` stages content; human approves Gate 3 via CLI; `promote.py` writes `wiki/` + `hermes_reflect.py` runs. Only `PROMOTED` writes canonical content. | D-002 (promote.py), D-004 (hermes) | Promotion chain in graph | B-008, D-002, D-004 | Staged content exists before Gate 3; `wiki/` unchanged before `PROMOTED`; Hermes appended after `PROMOTED` | T009 | Wiki pollution, Hermes timing wrong |
| B-010 | Implement cancellation handling | Cancel command transitions job to `CANCELLED` from any non-terminal state. Lock removed. Staged artifacts purged if present. | B-001, `job_lifecycle_spec.md` §1.3 | Cancellation logic in daemon and graph | B-001, B-004 | Cancel at each state; verify lock removed, status = `CANCELLED`, staged purged when applicable | — | Orphaned locks and staged files |

### BLOCK C: Router Integration

| ID | Title | Purpose | Inputs | Outputs | Depends On | Acceptance Criteria | Related Tests | Risk if Skipped |
|---|---|---|---|---|---|---|---|---|
| C-001 | Create `apps/llm_router/router.py` (unified) | New router that reads `routing_config.yaml`, dispatches to providers, enforces fallback chain and provider-switch budget (max 2). | Discovery report A-006, `routing_config.yaml` | `apps/llm_router/router.py`; old router kept at `apps/crewai_crews/llm_router.py` | A-006, A-010 | Router dispatches to correct provider per context; fallback activates on timeout/5xx; budget exhausted → raise | T004, T013 | Wrong provider, infinite fallback loops |
| C-002 | Port NIM provider from `nim_router.py` | NIMClient integrated into new router as a provider. `NVIDIA_API_KEY` primary, `NIM_API_KEY` fallback. | `nim_router.py` (code-verified), C-001 | NIM provider in new router | C-001 | `get_client("nim_fast")` returns NIMClient; chat completion succeeds with real key | T004, T005 | NIM tier non-functional |
| C-003 | Port Ollama provider from old router | Ollama provider migrated to new router. Local endpoint confirmed. | Old `llm_router.py`, A-009 | Ollama provider in new router | C-001, A-009 | `get_client("classify_local")` returns Ollama client; chat completion succeeds | T004 | Fallback safety net missing |
| C-004 | Port paid providers (Claude/Gemini/OpenAI) | Existing paid providers migrated to new router. No functional changes. | Old `llm_router.py` | Paid providers in new router | C-001 | `get_client("coding")`, `get_client("research")` etc. return correct clients | — | Regression in existing capability |
| C-005 | Create Kimi provider adapter | `apps/llm_router/providers/kimi.py`. OpenAI-compatible client with `https://api.moonshot.cn/v1` base URL. ~20 lines. | Kimi Open Platform docs, `openai` SDK | `apps/llm_router/providers/kimi.py` | C-001 | `get_client("exploration")` returns Kimi client; chat format identical to OpenAI | — | U-04 remains unblocked |
| C-006 | Wire `router_node` into LangGraph | `apps/runtime/nodes/router_node.py` calls `classify_job_file()` and sets `routing_context` in LangGraph state. | `complexity_scorer.py`, C-001, B-004 | `router_node.py`; graph updated to include it | A-007, C-001, B-004 | `router_node` classifies job; sets `routing_context` (e.g., "nim_fast"); downstream node uses it | — | NIM tier never invoked |
| C-007 | Implement provider-switch budget enforcement | Router tracks switches per job; after 2 switches, raises `ProviderBudgetExhausted`. | C-001, ADR-001 §5.2 | Budget enforcement in router | C-001 | Mock 2 failing providers; 3rd call raises `ProviderBudgetExhausted`; job transitions to `FAILED` | T013 | Cost explosion from infinite fallback |
| C-008 | Create `.env.example` | Standardize all API keys and local service URLs. Both `NVIDIA_API_KEY` and `NIM_API_KEY` listed. | All provider configs | `.env.example` | C-001..C-005 | File lists all 6 keys + Ollama URL; comments explain fallback priority | T005 | Operator confusion on key setup |
| C-009 | Verification: old router vs. new router parity | Run same tasks through both routers; outputs must match for non-NIM contexts. | Old router, new router | Parity report | C-001..C-004 | 10 tasks per context; 0 regressions | — | Silent regression in existing behavior |

### BLOCK D: Audit / Promote / Knowledge Integrity

| ID | Title | Purpose | Inputs | Outputs | Depends On | Acceptance Criteria | Related Tests | Risk if Skipped |
|---|---|---|---|---|---|---|---|---|
| D-001 | Create/adapt `scripts/audit.py` | Lightweight audit gate: regex secret scan (AWS keys, API tokens), file existence checks. Returns WARN or FAIL. | Discovery report A-003, `job_lifecycle_spec.md` | `scripts/audit.py` | A-003, A-010 | Script runs; secret pattern detected → FAIL; clean artifact → PASS; exit code matches result | T006, T012, T016 | No quality gate |
| D-002 | Create/adapt `scripts/promote.py` | Wiki promotion script: validates `audit_result == pass`, validates `approved_gate_3_by` exists, copies staged `raw/` → `wiki/`. Never writes without approval. | Discovery report A-004, `job_lifecycle_spec.md` §1.1, §1.4 | `scripts/promote.py` | A-004, A-010, D-001 | Without Gate 3 approval → exit 1, wiki unchanged. With approval → wiki updated. Audit FAIL blocks promotion. | T006, T009 | Wiki pollution, unauthorized writes |
| D-003 | Create/adapt `scripts/hermes_reflect.py` | One-way reflection: appends `wiki/` change summary to `runtime/hermes/memory.md`. Runs only after `PROMOTED`. Append-only. | Discovery report A-005 | `scripts/hermes_reflect.py` | A-005, A-010 | Runs after promotion; appends to Hermes memory; never reads Hermes as input | T012 | Hermes not populated; tactical memory gap |
| D-004 | Enforce knowledge boundaries in implementation | `audit.py` checks that no evidence sources include `runtime/hermes/` paths. `promote.py` rejects writes to `wiki/` from non-`PROMOTED` states. | `job_lifecycle_spec.md` §0 | Boundary enforcement in audit.py and promote.py | D-001, D-002 | Evidence with `runtime/hermes/` path → audit FAIL; promote.py called outside `PROMOTED` → exit 1 | T012 | Hermes becomes canonical by accident |
| D-005 | Distinguish `AUDIT_FAILED` from `GATE_2_REJECTED` in code | Separate state handling, separate log events, separate metrics counters. | `job_lifecycle_spec.md` §C2 | Distinct state machine branches | B-007, B-008 | `AUDIT_FAILED` job has `audit_result: fail`; `GATE_2_REJECTED` job has `status: gate_2_rejected`, `rejected_gate: 2`, `rejected_by`, `rejected_at`, and `reject_reason`; metrics separate | T016 | Cannot distinguish automated failure from human rejection |
| D-006 | Implement staged artifact cleanup on cancel | `promote.py` or daemon purges `work/artifacts/staging/JOB-###/` when job is cancelled after `PROMOTION_PENDING` or `APPROVED_GATE_3`. | `job_lifecycle_spec.md` §1.3 | Cleanup logic | B-010, D-002 | Cancel `PROMOTION_PENDING` job → staging directory deleted; cancel earlier states → staging untouched | — | Orphaned staging files accumulate |

### BLOCK E: Verification Automation

| ID | Title | Purpose | Inputs | Outputs | Depends On | Acceptance Criteria | Related Tests | Risk if Skipped |
|---|---|---|---|---|---|---|---|---|
| E-001 | Create `tests/conftest.py` | Shared pytest fixtures: temp directories, mock NIM/Ollama clients, fake job files, corrupted state generator. | All blocks | `tests/conftest.py` | — | Fixtures provide: `tmp_job_dir`, `mock_nim_client`, `mock_ollama_client`, `corrupted_state` | All tests | No shared infrastructure |
| E-002 | Implement `tests/test_daemon.py` | T001 (duplicate claim), T002 (corrupted state recovery), T003 (stale lock reclaim). | B-001, B-002, B-003, E-001 | `tests/test_daemon.py` | B-001..B-003, E-001 | All 3 tests pass in < 30s each; no persistent state left | T001, T002, T003 | No daemon safety verification |
| E-003 | Implement `tests/test_router.py` | T004 (fallback), T005 (missing credentials), T013 (budget exhaustion). | C-001..C-007, E-001 | `tests/test_router.py` | C-001..C-007, E-001 | All 3 tests pass; mock providers used for T013 | T004, T005, T013 | No router safety verification |
| E-004 | Implement `tests/test_hitl.py` | T007 (Gate 1 blocks), T008 (Gate 2 blocks), T009 (Gate 3 blocks), T015 (idempotent re-run), T016 (audit vs rejection distinction). | B-004..B-009, D-005, E-001 | `tests/test_hitl.py` | B-004..B-009, D-005, E-001 | All 5 tests pass; T016 verifies distinct states and log events | T007, T008, T009, T015, T016 | No HITL enforcement verification |
| E-005 | Implement `tests/test_audit_promote.py` | T006 (audit FAIL blocks promote), T012 (Hermes not canonical). | D-001, D-002, D-004, E-001 | `tests/test_audit_promote.py` | D-001, D-002, D-004, E-001 | Both tests pass; temp wiki and Hermes directories used | T006, T012 | No audit/knowledge integrity verification |
| E-006 | Implement `tests/test_ingress.py` | T011 (CLI-only, no external dependencies). | B-001, E-001 | `tests/test_ingress.py` | B-001, E-001 | Test passes with no network; no Slack imports detected | T011 | External service dependency sneaks in |
| E-007 | Document T014 manual procedure | Operator checklist for daemon restart mid-execution verification. | B-001..B-003, `job_lifecycle_spec.md` §5.1 | `docs/T014_manual_procedure.md` | B-001..B-003 | Documented: setup steps, expected outcome, pass/fail criteria, estimated time (15 min) | T014 | No manual verification for crash safety |
| E-008 | Run full test suite and fix failures | Execute all tests; fix any failures; re-run until green. | E-002..E-007 | All-green CI report | E-002..E-007 | `pytest tests/` returns 0 failures; all 13 automated tests pass | All | Untested code ships |

### BLOCK F: Release Readiness

| ID | Title | Purpose | Inputs | Outputs | Depends On | Acceptance Criteria | Related Tests | Risk if Skipped |
|---|---|---|---|---|---|---|---|---|
| F-001 | Execute T014 manual verification | Run documented manual procedure; record result. | E-007, running system | T014 sign-off record | E-007, all Blocks A-E | Procedure completed; result recorded as PASS or FAIL with notes | T014 | Crash safety unverified |
| F-002 | Verify zero security-breach test failures | Confirm T006, T007, T008, T009, T012, T016 all pass. | E-008 test results | Security clearance report | E-008 | All 6 tests green; any failure documented as P0 blocker | T006, T007, T008, T009, T012, T016 | Security vulnerability ships |
| F-003 | Final scope freeze confirmation | Verify no deferred items were added during implementation. | Final codebase, `mvp_scope_freeze.md` | Scope compliance report | All blocks | No Qdrant imports; no Slack imports; no checkpoint resume logic; no Data Flywheel evaluation | — | Scope creep undetected |
| F-004 | Produce MVP release notes | Document verified capabilities, known limitations, and P1 roadmap. | All blocks, all verification | `docs/MVP_RELEASE_NOTES.md` | F-001..F-003 | Notes list: what's in, what's deferred, what's rejected, operator instructions | — | Operator confusion post-release |
| F-005 | MVP release approval | Final sign-off. | F-001..F-004 | Release decision: GO / NO-GO | F-001..F-004 | All release criteria met or explicitly waived with CEO approval | All | Premature release |

---

## 4. P0 Discovery Tasks (Block A Detail)

These are the nine verification tasks that must complete before any implementation block begins. They are ordered by dependency and risk.

```
A-001 (graph.py) ──┐
A-002 (daemon) ────┤
A-003 (audit.py) ──┤
A-004 (promote.py)─┤
A-005 (hermes) ────┤──→ A-010 (decision record)
A-006 (NIM patch) ─┤
A-007 (scorer run)─┤
A-008 (NIM conn) ──┘
A-009 (Ollama) ────┘
```

**A-001: Verify `graph.py`**
- Action: `find Kinetic_Protocol/ -name "graph.py" -type f`
- If found: inspect imports (langgraph? SqliteSaver? interrupt?)
- If not found: decision = BUILD `apps/runtime/graph.py` from scratch
- Time estimate: 15 min

**A-002: Verify `wiki_daemon.py`**
- Action: `find . -name "*daemon*.py" -type f` across all 5 repos
- If found: inspect for watchdog, status transitions, lock handling
- If not found: decision = BUILD `apps/daemon/wiki_daemon.py` from scratch
- Time estimate: 15 min
- **Risk: HIGH** — this is the biggest unknown in the system

**A-003: Verify `audit.py`**
- Action: `find . -name "audit.py" -type f`
- If found: inspect for WARN/FAIL logic, secret scan patterns
- If not found: decision = BUILD lightweight `scripts/audit.py`
- Time estimate: 15 min

**A-004: Verify `promote.py`**
- Action: `find . -name "promote.py" -type f`
- If found: inspect for `approved_gate_2_by`/`approved_gate_3_by` frontmatter verification, wiki write logic
- If not found: decision = BUILD `scripts/promote.py`
- Time estimate: 15 min

**A-005: Verify `hermes_reflect.py`**
- Action: `find . -name "hermes_reflect.py" -type f`
- If found: inspect for append-only behavior
- If not found: decision = BUILD `scripts/hermes_reflect.py` (~30 lines)
- Time estimate: 15 min

**A-006: Verify NIM patch on `llm_router.py`**
- Action: `grep -n "NIMClient\|nim_fast\|nim_large" Kinetic_Protocol/apps/crewai_crews/llm_router.py`
- If NIMClient found: patch is applied
- If not found: decision = APPLY 4-line patch from handover
- Time estimate: 10 min

**A-007: Execute `complexity_scorer.py`**
- Action: `cd Kinetic_Protocol && python apps/crewai_crews/complexity_scorer.py "Analyze FF14 patch 7.1"`
- Expected: JSON output with `level` and `recommended_context` fields
- If fails: debug Ollama connectivity or fix script
- Time estimate: 10 min

**A-008: Verify real NIM connectivity**
- Action: `cd Kinetic_Protocol && python apps/crewai_crews/nim_router.py`
- Expected: Chat response from `meta/llama-3.1-8b-instruct`
- Requires: `NVIDIA_API_KEY` in environment
- If fails: obtain key at https://build.nvidia.com
- Time estimate: 5 min (if key exists) or unknown (if key needed)

**A-009: Verify Ollama runtime and models**
- Action: `ollama list && ollama ps`
- Expected: `qwen2.5:7b`, `qwen2.5-coder:7b`, `gemma2:27b` listed
- If models missing: `ollama pull qwen2.5:7b`
- Time estimate: 5 min

---

## 5. Critical Path

The minimum chain of tasks that must complete to reach a releasable MVP:

```
A-002 (daemon existence) → A-010 (decision: BUILD or ADAPT daemon)
  → B-001 (daemon implementation)
    → B-002 (state rebuild)
      → B-003 (stale-lock reclaim)
        → E-002 (daemon tests pass) ──────────────────────┐
                                                             │
A-001 (graph.py existence) → A-010 (decision: BUILD or ADAPT graph)
  → B-004 (graph implementation)
    → B-005 (Gate 1)
      → B-006 (crew_execute_node)
        → B-007 (audit_node)
          → B-008 (Gate 2 + GATE_2_REJECTED)
            → B-009 (promotion chain)
              → E-004 (HITL tests pass) ──────────────────┤
                                                             │
A-006 (NIM patch status) → A-010
  → C-001 (unified router)
    → C-002 (NIM provider)
      → C-003 (Ollama provider)
        → C-006 (router_node wiring)
          → E-003 (router tests pass) ──────────────────────┤
                                                             │
A-003 (audit existence) → A-010
  → D-001 (audit.py)
    → D-002 (promote.py)
      → D-004 (boundary enforcement)
        → D-005 (AUDIT_FAILED vs GATE_2_REJECTED)
          → E-005 (audit/promote tests pass) ───────────────┤
                                                             │
E-001 (conftest) → E-006 (ingress test pass) ──────────────┤
                                                             │
E-007 (T014 manual procedure) → F-001 (T014 executed) ──────┤
                                                             │
F-002 (security tests verified) → F-003 (scope confirmed)   │
                                    → F-004 (release notes)  │
                                      → F-005 (release GO) ◄─┘
```

**Critical path duration estimate:** 5–7 work days assuming 1 developer, with Block A completing in Day 1 and parallel work on Blocks B, C, D beginning Day 2.

---

## 6. Release Gate Mapping

| Verification Test | Must Pass After WBS Task | Blocking If Fails |
|---|---|---|
| T001 Duplicate claim prevention | E-002 (after B-001, B-002) | Double execution |
| T002 Corrupted state recovery | E-002 (after B-002) | Lost jobs |
| T003 Stale lock reclaim | E-002 (after B-003) | Orphaned jobs |
| T004 Router fallback | E-003 (after C-001, C-002, C-003) | No NIM fallback |
| T005 Missing credentials fail-fast | E-003 (after C-002) | Silent security failures |
| T006 Audit FAIL blocks promotion | E-005 (after D-001, D-002, D-004) | Secret promotion to wiki |
| T007 Gate 1 blocks execution | E-004 (after B-005) | Runaway execution |
| T008 Gate 2 blocks promotion | E-004 (after B-008) | Bad artifacts promoted |
| T009 Gate 3 blocks wiki write | E-004 (after B-009) | Wiki pollution |
| T011 CLI-only operation | E-006 (after B-001) | External service dependency |
| T012 Hermes not canonical | E-005 (after D-004) | Factual drift |
| T013 Provider budget exhaustion | E-003 (after C-007) | Cost explosion |
| T015 Idempotent re-run | E-004 (after B-004) | Cross-job contamination |
| T016 Audit vs rejection distinction | E-004 (after D-005) | Cannot distinguish failures |
| T014 Daemon restart (manual) | F-001 (after E-007) | Crash safety unverified |

**Security-breach tests (must all pass):** T006, T007, T008, T009, T012, T016.

---

## 7. Scope Guardrails

During WBS execution, the following temptations must be explicitly rejected:

| # | Temptation | Why It Must Be Rejected | Detection |
|---|---|---|---|
| 1 | "Let's add Slack notifications for HITL gates — it'll be quick" | Slack is deferred to P1. Adding it now introduces Bolt dependency, webhook setup, and OAuth complexity. | Any import of `slack_bolt` or `slack_sdk` in runtime code is a scope violation. |
| 2 | "Let's integrate Qdrant for RAG — the research node needs it" | Qdrant is deferred. MVP loads knowledge from flat Markdown files. | Any import of `qdrant_client` or reference to `localhost:6333` in runtime code. |
| 3 | "Let's make checkpoint resume automatic — SqliteSaver is already there" | Checkpoint resume is P1. MVP safely fails the job on daemon crash. Operator clones to new JOB. | Any code that calls `graph.resume_from_checkpoint()` or equivalent. |
| 4 | "Let's add multiple CrewAI crews for parallel execution" | Single crew per job per ADR-001. Multi-crew adds debugging complexity. | Any code that instantiates more than one `Crew` per job. |
| 5 | "Let's make promote.py auto-trigger on audit PASS" | Violates HITL Gate 3 invariant. `promote.py --mode execute` requires explicit `approved_gate_2_by` and `approved_gate_3_by` metadata in the JOB frontmatter. | Any event listener or callback that calls `promote.py` without human approval metadata. |
| 6 | "Let's merge AUDIT_FAILED and GATE_2_REJECTED for simplicity" | They must remain distinct per lifecycle spec. Conflating them breaks metrics and debugging. | Any code path that assigns `audit_result: fail` when the human rejected at Gate 2. |
| 7 | "Let's write to wiki/ from APPROVED_GATE_3 instead of PROMOTED" | `PROMOTED` is the only state that writes canonical wiki content. `APPROVED_GATE_3` is metadata only. | Any write to `wiki/` outside the `PROMOTED` transition handler. |
| 8 | "Let's add Data Flywheel JSONL evaluation" | Data Flywheel is Phase 2. MVP saves logs only (`model_calls.jsonl`, `job_results.jsonl`). No evaluation loop. | Any code that reads `model_calls.jsonl` to compute metrics or trigger model selection. |
| 9 | "Let's add dynamic model loading from model_policy.yaml" | Model selection is static `routing_config.yaml` only. No per-request overrides. | Any `model_override` parameter in router functions. |
| 10 | "Let's keep the old llm_router.py and new router.py in sync" | Old router is temporary. Do not maintain parity after C-009 passes. Remove after 10 end-to-end jobs. | Any commit that modifies `apps/crewai_crews/llm_router.py` after C-009 is complete. |

**Enforcement:** Before any commit, run `scripts/scope_guard.sh` (to be created in Block A) that greps for forbidden imports, forbidden patterns, and forbidden state transitions. A failing scope guard blocks the commit.

---

*WBS Version: 1.0*
*Frozen against: mvp_scope_freeze.md (Freeze-001), job_lifecycle_spec.md (1.0-FROZEN), verification_plan.md (1.0), ADR-001-mvp-control-plane.md*
*Next action: Execute Block A (P0 Discovery Tasks) and record A-010 decision log.*
