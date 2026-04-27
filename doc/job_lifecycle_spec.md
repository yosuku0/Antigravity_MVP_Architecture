# Job Lifecycle Specification
## NIM-Kinetic Meta-Agent MVP
## Version: 1.0-FROZEN
## Date: 2026-04-24

---

## 0. Knowledge Boundaries (Non-Negotiable)

These boundaries are enforced by convention, file permissions, and `audit.py`. Blurring them is a FAIL condition.

| Directory | Role | Writable By | Canonical? | Promotion Path |
|---|---|---|---|---|
| `raw/` | Draft knowledge, unverified sources, scraped content | Brain, ingestion scripts | **NO** | → `wiki/` via `promote.py` only |
| `work/` | Active jobs, locks, volatile artifacts, scratch pads | Daemon, LangGraph nodes, crews | **NO** | → `memory/working/` temporary only |
| `work/jobs/` | JOB definitions and state | Brain (create), Daemon (status), Executor (evidence/artifacts) | **YES** for job state | No promotion |
| `wiki/` | Canonical knowledge, approved facts, Source of Truth | `promote.py` ONLY (post Gate 3) | **YES** | Terminal — no further promotion |
| `memory/long_term/` | Cross-repo procedural memory, ADRs, decisions | `hermes_reflect.py`, manual CEO edit | **NO** (procedural, not factual) | One-way from `wiki/` |
| `memory/working/` | Per-job scratch space, ephemeral | Executor during job | **NO** | Auto-purged after job completion |
| `runtime/hermes/` | Tactical style, private agent memory, reflections | `hermes_reflect.py` ONLY | **NO** | One-way from `wiki/` only |

**Invariant:** `wiki/` is the only canonical Source of Truth for domain facts. `runtime/hermes/` is tactical memory and must never be treated as canonical. If a future implementation reads Hermes memory to answer a factual question, that is a design bug.

**Invariant:** No write to `wiki/` is permitted before HITL Gate 3 approval. `promote.py --mode execute` must verify that the JOB is in `approved_gate_3` and that required Gate 2 / Gate 3 approval metadata exists in frontmatter, especially `approved_gate_2_by` and `approved_gate_3_by`.

---

## 1. State Machine Definition

### 1.1 States

| State | Code | Entry Condition | Exit Condition | Files Written | Idempotency | Retry Allowed | Human Approval | Recovery After Daemon Restart |
|---|---|---|---|---|---|---|---|---|
| **CREATED** | `created` | Brain writes JOB-###.md with `status: created` | Human approves Gate 1 | `work/jobs/JOB-###.md` (initial) | Yes — overwrite idempotent if same content hash | N/A | **Gate 1 required** | Re-scan `work/jobs/`; transition to CREATED if file exists and status is `created` or `pending` |
| **APPROVED_GATE_1** | `approved_gate_1` | Human approves via CLI only | Daemon detects `status: approved_gate_1` | JOB-###.md updated with `approved_by`, `approved_at` | Yes — re-approval is no-op if already approved | N/A | Already obtained | If daemon missed approval event, rescan JOB file and transition if `status == approved_gate_1` |
| **CLAIMED** | `claimed` | Daemon detects approved JOB; acquires lock | Lock acquired successfully | `work/locks/JOB-###.lock` (atomic create) | **No** — duplicate claim must fail | No — claim is single-shot | No | If lock exists but `daemon_state.json` shows no active owner, validate lock age; if > 10 min, reclaim (see stale-lock rule) |
| **ROUTED (Internal)** | `routed` | `router_node` completes; `complexity_scorer` returns context | Routing context written to state | JOB-###.md updated with `routing_context` | Yes — re-routing same job is idempotent if task unchanged | No — routing is deterministic | No | Conceptual/Internal only (collapsed into EXECUTING in implementation). Re-run `router_node` if `routing_context` missing in state |
| **EXECUTING** | `executing` | LangGraph enters `crew_execute_node` or equivalent | Node completes (success or caught exception) | `memory/working/JOB-###/` artifacts; logs appended | No — MVP does not auto-resume from checkpoint (P1). Job transitions to FAILED on daemon restart. | Yes — per ADR-001: max 3 node retries, max 5 total | No (already approved at Gate 1) | Daemon restart → transition to `FAILED`. If checkpoint exists: `reason: checkpoint_resume_deferred`. If no checkpoint: `reason: no_checkpoint`. Operator clones to new JOB. |
| **AUDIT_FAILED** | `audit_failed` | `audit.py` returns FAIL or WARN>0 | Human sends back for rework, or human cancels | JOB-###.md updated with `audit_result: fail`, `audit_log` | Yes — re-audit is idempotent | Yes — max 2 re-execution attempts after fixes | No — automated failure, not human decision | State is terminal until human sends back to EXECUTING or cancels |
| **GATE_2_REJECTED** | `gate_2_rejected` | Human explicitly rejects artifact at Gate 2 | Human sends back for rework, or human cancels | JOB-###.md updated with `rejected_gate`, `rejected_by`, `rejected_at`, `reject_reason` | Yes — rejection is recorded once | Yes — max 2 re-execution attempts after fixes | **YES** — human explicitly rejected | State is terminal until human sends back to EXECUTING or cancels. Distinguishable from AUDIT_FAILED in logs and metrics. `rejected_gate: 2` identifies the gate. |
| **AUDIT_PASSED** | `audit_passed` | `audit.py` returns WARN=0, FAIL=0 | Human approves Gate 2 | JOB-###.md updated with `audit_result: pass` | Yes — re-audit is idempotent | N/A | **Gate 2 required** | If status is `audit_passed` but no `approved_gate_2` field, wait for human approval |
| **APPROVED_GATE_2** | `approved_gate_2` | Human approves artifact via Slack or CLI | `promote.py` invoked by daemon | JOB-###.md updated with `approved_gate_2_by`, `approved_gate_2_at` | Yes — re-approval no-op | N/A | Already obtained | Rescan and proceed if fields present |
| **PROMOTION_PENDING** | `promotion_pending` | `promote.py --mode stage` completes staging | Gate 3 human approval | `raw/` → `work/artifacts/staging/JOB-###/`; `promote_manifest.md` generated. **No write to `wiki/` occurs in this state.** | No — partial staging is a failure | Yes — promote.py may retry staging once on filesystem error | No (already approved at Gate 2) | If staging exists but `status != promotion_pending`, treat as orphaned staging; purge after 24h |
| **APPROVED_GATE_3** | `approved_gate_3` | Human approves staged promotion via **CLI only** | `promote.py --mode execute` invoked by daemon | `approved_gate_3_by` and `approved_gate_3_at` recorded in JOB-###.md. **No write to `wiki/` yet** — approval is metadata only. | **No** — approval record is write-once | N/A | **Gate 3 required (CLI only)** | If `wiki/` pages exist but `approved_gate_3` missing in JOB, treat as unauthorized write; trigger security alert |
| **PROMOTED** | `promoted` | `promote.py --mode execute` completes wiki write | Terminal state | `wiki/` receives new/updated pages (ONLY in this state); `runtime/hermes/memory.md` appended; `logs/promotions.jsonl` entry | No — wiki write is not idempotent | N/A | Already obtained (Gate 3) | Terminal — no recovery needed. `hermes_reflect.py` may be re-run safely (append-only) but wiki write must not repeat. |
| **FAILED** | `failed` | Unrecoverable error, budget exhaustion, or explicit cancel | Terminal state | JOB-###.md updated with `status: failed`, `failure_reason`, `failure_node` | Yes — terminal, no action | No | No | Terminal — requires manual review; may be cloned into new JOB |
| **CANCELLED** | `cancelled` | Human issues cancel command at any point before `PROMOTED` | Terminal state | `work/locks/JOB-###.lock` removed; `status: cancelled`; staged artifacts purged if present | Yes — idempotent | No | Human-initiated | Terminal — cleanup only. Cancellation after `PROMOTED` is a no-op (job is complete). |

### 1.2 Valid Transitions

```
CREATED
  → APPROVED_GATE_1   [human approves]
  → CANCELLED         [human cancels]

APPROVED_GATE_1
  → CLAIMED           [daemon detects and locks]
  → CANCELLED         [human cancels before claim]

CLAIMED
  → ROUTED            [router_node completes]
  → FAILED            [lock acquisition fails irrecoverably]
  → CANCELLED         [human cancels before routing]

ROUTED
  → EXECUTING         [execution node starts]
  → FAILED            [routing error (e.g., unknown context)]
  → CANCELLED         [human cancels before execution]

EXECUTING
  → AUDIT_PASSED      [audit.py passes]
  → AUDIT_FAILED      [audit.py fails]
  → FAILED            [uncaught exception / retry budget exhausted]
  → CANCELLED         [human cancels during execution]

AUDIT_FAILED
  → EXECUTING         [human sends back for rework — max 2 times]
  → FAILED            [rework budget exhausted]
  → CANCELLED         [human cancels]

GATE_2_REJECTED
  → EXECUTING         [human sends back for rework — max 2 times]
  → FAILED            [rework budget exhausted]
  → CANCELLED         [human cancels]

AUDIT_PASSED
  → APPROVED_GATE_2   [human approves artifact]
  → GATE_2_REJECTED   [human rejects artifact]
  → CANCELLED         [human cancels]

APPROVED_GATE_2
  → PROMOTION_PENDING [promote.py stages content]
  → CANCELLED         [human cancels before promotion]

PROMOTION_PENDING
  → APPROVED_GATE_3   [human approves staged promotion]
  → FAILED            [promote.py crashes irrecoverably during staging]
  → CANCELLED         [human cancels]

APPROVED_GATE_3
  → PROMOTED          [promote.py --mode execute writes wiki + hermes]
  → FAILED            [filesystem error during wiki write]
  → CANCELLED         [human cancels before wiki write. Note: **Rejection is unsupported at Gate 3 in MVP.**]

PROMOTED
  → (terminal)

FAILED
  → (terminal — may be cloned to new JOB)

CANCELLED
  → (terminal)
```

### 1.3 Cancellation Semantics (Explicit Rules)

Cancellation is **allowed** from any state except terminal states (`PROMOTED`, `FAILED`, `CANCELLED`).

| State at Cancel | Lock File | Staged Artifacts | JOB Status | Working Dir |
|---|---|---|---|---|
| Before `CLAIMED` | Not yet created | None | `CANCELLED` | None |
| `CLAIMED` through `EXECUTING` | Removed | None | `CANCELLED` | Preserved for debugging (manual purge) |
| `AUDIT_FAILED` / `GATE_2_REJECTED` | Removed | None | `CANCELLED` | Preserved for debugging |
| `APPROVED_GATE_2` | Removed | None | `CANCELLED` | Preserved for debugging |
| `PROMOTION_PENDING` | Removed | **Purged** (`work/artifacts/staging/JOB-###/` deleted) | `CANCELLED` | Preserved |
| `APPROVED_GATE_3` | Removed | **Purged** | `CANCELLED` | Preserved |
| `PROMOTED` | N/A | N/A | No-op (already terminal) | N/A |

**Cancellation after `APPROVED_GATE_2` is explicitly allowed.** The human may change their mind after approving the artifact but before wiki write. Staged artifacts are purged; the job is `CANCELLED`. This is not an invalid transition.

### 1.4 Invalid Transitions (Hard Errors)

These transitions are bugs if they occur:

| Invalid Transition | Detection | Response |
|---|---|---|
| `CREATED` → `EXECUTING` (skips Gate 1) | `entry_node` status check | Security alert; block execution; log incident |
| `AUDIT_FAILED` → `PROMOTED` (skips rework + Gate 2) | `promote.py` validates `audit_result == pass` AND `approved_gate_2_by` exists | Refuse promotion; log incident |
| `GATE_2_REJECTED` → `PROMOTED` (human said no) | `promote.py` validates `approved_gate_2_by` exists | Refuse promotion; log incident |
| `EXECUTING` → `PROMOTED` (skips audit + Gate 2) | `promote.py` validates `audit_result` and Gate 2 approval | Refuse promotion; log incident |
| `APPROVED_GATE_2` → `PROMOTED` (skips staging + Gate 3) | `promote.py` validates `approved_gate_3_by` exists | Refuse wiki write; log incident |
| `PROMOTION_PENDING` → `PROMOTED` (skips Gate 3) | `promote.py` validates `approved_gate_3_by` exists | Refuse wiki write; log incident |
| `CLAIMED` → `CREATED` (backward) | State machine validation | Log error; do not modify state |
| `PROMOTED` → anything | State machine validation | Log error; treat as new JOB if re-execution needed |

---

## 2. State Write Atomicity

### 2.1 JOB file updates

All writes to `work/jobs/JOB-###.md` must be atomic:

```python
import tempfile, os, shutil

def atomic_write_job(path: Path, content: str):
    tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, dir=path.parent, suffix='.tmp')
    tmp.write(content)
    tmp.flush()
    os.fsync(tmp.fileno())
    tmp.close()
    shutil.move(tmp.name, path)  # atomic on same filesystem
```

### 2.2 Lock files

Lock acquisition must use atomic file creation:

```python
# POSIX: O_CREAT | O_EXCL
def try_lock(job_id: str) -> bool:
    lock_path = Path(f"work/locks/{job_id}.lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w') as f:
            f.write(f"{datetime.now().isoformat()}\n{os.getpid()}\n")
        return True
    except FileExistsError:
        return False
```

### 2.3 daemon_state.json

`daemon_state.json` is a **cache**, not ground truth. Ground truth is always the union of:
1. `work/jobs/JOB-###.md` files (status in YAML frontmatter)
2. `work/locks/` directory (lock existence)
3. `logs/daemon.jsonl` (append-only event log)

On restart, the daemon **rebuilds** `daemon_state.json` from these three sources. It never trusts a stale `daemon_state.json` on disk.

---

## 3. Duplicate-Claim Prevention

### 3.1 Mechanism

Three layers:
1. **Filesystem lock:** `work/locks/JOB-###.lock` with `O_CREAT | O_EXCL`
2. **Daemon state:** In-memory `claimed_jobs: set[str]`
3. **JOB status gate:** Only `status: approved_gate_1` jobs are eligible for claim

### 3.2 Race condition resolution

If two daemon instances (or a daemon and a manual script) race:
- The atomic `O_EXCL` ensures exactly one succeeds.
- The loser logs `claim_rejected: already_locked` and moves to next pending job.
- If no next job exists, daemon sleeps `POLL_INTERVAL` (default 5s).

---

## 4. Stale-Lock Recovery

### 4.1 Detection

A lock is stale if:
- Lock file exists AND
- `daemon_state.json` (rebuilt from jsonl) shows no active process for this job AND
- Lock file mtime > 10 minutes old

### 4.2 Recovery

```python
if lock_stale(job_id):
    # 1. Archive the old lock
    archive_path = f"work/locks/archived/{job_id}_{timestamp}.lock"
    shutil.move(lock_path, archive_path)
    
    # 2. Transition job status based on last known state
    if last_state in {"executing", "routed"}:
        set_job_status(job_id, "failed", reason="stale_lock_recovered")
    elif last_state == "claimed":
        set_job_status(job_id, "approved_gate_1")  # re-eligible for claim
    
    # 3. Log recovery action
    append_daemon_log(event="stale_lock_recovered", job_id=job_id, archived_to=archive_path)
```

### 4.3 Safety

Stale-lock recovery never resumes execution. It either fails the job (if execution had started) or releases it for re-claim (if never routed). This prevents partial-execution artifacts from being treated as complete.

---

## 5. Partial-Failure Recovery

### 5.1 During EXECUTING

**MVP recovery path:** Daemon rebuilds state on restart. If `status == executing`:

| Scenario | MVP Behavior | P1 Behavior |
|---|---|---|
| Daemon crashes during execution, checkpoint exists | Transition to `FAILED` (`reason: checkpoint_resume_deferred`). Operator may manually clone to new JOB. | Resume from LangGraph `SqliteSaver` checkpoint. |
| Daemon crashes during execution, no checkpoint | Transition to `FAILED` (`reason: no_checkpoint`). | Same — `FAILED`. |
| Node retries exhausted | Transition to `FAILED` (`failure_reason: retry_budget_exhausted`). | Same. |
| Provider fallback exhausted | Transition to `FAILED` (`failure_reason: provider_budget_exhausted`). | Same. |
| Audit fails after execution | Transition to `AUDIT_FAILED`. Human may send back to `EXECUTING` (max 2 rework cycles). | Same. |
| Human rejects at Gate 2 | Transition to `GATE_2_REJECTED`. Human may send back to `EXECUTING` (max 2 rework cycles). | Same. |

**Why checkpoint resume is P1, not MVP:** Checkpoint resume requires LangGraph checkpoint introspection, resume-from-checkpoint wiring in `graph.py`, and precise testing of partial node re-execution. The MVP release is not blocked by this — the daemon rebuilds state correctly and fails the job safely. A human operator can clone the job and retry. This is acceptable for MVP operational safety.

### 5.2 During PROMOTION_PENDING

If `promote.py` crashes after staging files but before wiki write:
- Staging area is in `work/artifacts/staging/JOB-###/`
- On restart, if staging exists and `status == promotion_pending`, re-run `promote.py --resume JOB-###`
- `promote.py` must be idempotent for staging (safe to re-copy `raw/` files).
- Wiki write is NOT idempotent; it requires Gate 3 approval.

---

## 6. HITL Gates (Operational Definition)

| Gate | Trigger | Blocking? | Denial Behavior | Timeout Behavior |
|---|---|---|---|---|
| **Gate 1** | JOB created | **YES** — execution blocked until approved | Status → CANCELLED or stays CREATED (human may edit JOB) | No timeout. Jobs in CREATED > 7 days are auto-archived (not failed, just moved to `work/jobs/archived/`). |
| **Gate 2** | Audit passed | **YES** — promotion blocked until approved | Approval → `APPROVED_GATE_2`. Rejection → `GATE_2_REJECTED` (distinct from `AUDIT_FAILED`). Human may send back for rework from either state. | No timeout. |
| **Gate 3** | Staged promotion ready | **YES** — wiki write blocked until approved | Approval → `APPROVED_GATE_3` → `PROMOTED`. Rejection → `CANCELLED`; staging purged after 24h. | Staging purged after 24h if no approval. |

---

## 7. Summary Rules

1. **Ground truth is files, not memory.** `daemon_state.json` is rebuilt on every start from `work/jobs/` + `work/locks/` + `logs/daemon.jsonl`.
2. **Locks are atomic and time-bounded.** Stale locks (> 10 min) are archived and recovered, never ignored.
3. **No backward transitions.** A job only moves forward or to terminal states.
4. **Promotion requires three approvals.** No automation bypasses any gate. `wiki/` is written only in `PROMOTED` state.
5. **Hermes is append-only and non-canonical.** `runtime/hermes/` receives reflections only after `PROMOTED`; it never feeds back into `wiki/`.
6. **Partial execution is not auto-resumed in MVP.** Daemon detects `EXECUTING` job on restart → if no checkpoint, `FAILED`. If checkpoint exists, `FAILED` with `reason: checkpoint_resume_deferred`. Operator clones to new JOB. P1 will add checkpoint resume.
7. **Retry and provider budgets are finite.** Exhaustion → `FAILED`, not infinite loop.
8. **AUDIT_FAILED and GATE_2_REJECTED are distinct.** Automated audit failures and human rejections have separate states, separate log entries, and separate metrics.
9. **Cancellation is allowed before `PROMOTED`.** After `PROMOTED`, cancellation is a no-op. Staged artifacts are purged on cancel.

---

*Specification version: 1.0-FROZEN*
*Next revision: After first 5 end-to-end jobs or upon ADR-001 amendment.*
