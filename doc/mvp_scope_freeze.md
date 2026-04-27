# MVP Scope Freeze Document
## NIM-Kinetic Meta-Agent MVP
## Version: Freeze-001
## Date: 2026-04-24
## Status: FROZEN — No additions without CEO approval

---

## 1. Included in MVP Scope

| # | Capability | Rationale | Dependency Risk | Supported in MVP | Required for Release |
|---|---|---|---|---|---|
| 1 | **CLI ingress** (`/agent` or direct command) | Single lowest-friction entry point. No external service dependencies. Slack is deferred; CLI is the only MVP ingress. | None | **YES** | **YES** |
| 2 | **JOB-###.md generation** from CLI intent | Canonical work contract is the non-negotiable core. Without this, nothing else matters. | None | **YES** | **YES** |
| 3 | **LangGraph StateGraph** as primary orchestrator | Provides state machine, SQLite checkpointing, and interrupt primitives for HITL gates. | Low — pip-installable | **YES** | **YES** |
| 4 | **NIM-first LLM Router** (`llm_router.py`) | The MVP justification is filling the gap between Ollama 7B and paid APIs. NIM tier must work. | Medium — needs `NVIDIA_API_KEY` | **YES** | **YES** |
| 5 | **Ollama fallback** (`classify_local`, cheap-first) | Operational safety net. Must work when NIM is unreachable or for trivial tasks. | Low — Ollama confirmed running | **YES** | **YES** |
| 6 | **Claude/Gemini/OpenAI paid providers** | Already exist in current `llm_router.py`. Keep operational; no new work. The core MVP loop does not depend on them. | Low — already implemented | **YES** | **NO** |
| 7 | **Kimi provider adapter** | `exploration` context assigned to Kimi per Design Doc §2.2. The core MVP loop (NIM→Ollama) does not require Kimi. | Low — OpenAI SDK compatible | **YES** | **NO** |
| 8 | **`complexity_scorer.py` → router integration** (`router_node`) | `classify_job_file()` exists (handover verified). Wire it into LangGraph. Without this, NIM tier is unused. | Low — code exists, needs wiring | **YES** | **YES** |
| 9 | **Audit gate** (`audit.py`) with WARN/FAIL output | Must block promotion on failure. Lightweight regex + file checks for MVP. | Medium — need to verify script exists | **YES** | **YES** |
| 10 | **HITL Gate 1** (JOB approval before execution) | Prevents runaway agent execution. LangGraph `interrupt_before("execute")`. CLI approval only. | Low — LangGraph primitive | **YES** | **YES** |
| 11 | **HITL Gate 2** (artifact approval before merge/promotion) | Prevents bad artifacts from advancing. CLI approval only. Mandatory per security constraints. | Low — CLI prompt | **YES** | **YES** |
| 12 | **HITL Gate 3** (wiki promotion approval) | Prevents pollution of canonical knowledge. CLI approval only. `promote.py --mode execute` verifies required Gate 2 and Gate 3 approval metadata from JOB frontmatter, especially `approved_gate_2_by` and `approved_gate_3_by`. | Low — CLI prompt | **YES** | **YES** |
| 13 | **`wiki_daemon` — minimal JOB detection + recovery** | File-watcher on `work/jobs/`, atomic locks, state transitions, `daemon_state.json` rebuild from ground truth on restart, stale-lock reclaim. Checkpoint-based job resume is P1 (see item 8 in Deferred). | Medium — may not exist in code yet | **YES** | **YES** |
| 14 | **SQLite checkpoint persistence** (`SqliteSaver`) | Bundled with LangGraph. Saves checkpoint state for future resume capability. Automatic resume from checkpoint is P1, not MVP. | None | **YES** | **NO** |
| 15 | **Structured JSONL logging** (`model_calls.jsonl`, `job_results.jsonl`) | Operational visibility and Data Flywheel future-proofing. Appending to file is trivial. | None | **YES** | **YES** |
| 16 | **`raw/` → `wiki/` boundary enforcement** | Knowledge layer integrity. `raw/` is draft space; `wiki/` is canonical. Only `promote.py` writes to `wiki/`, and only in `PROMOTED` state. | None — policy only | **YES** | **YES** |
| 17 | **Hermes memory append** (`hermes_reflect.py`) | One-way reflection from wiki to tactical memory. Runs only after `PROMOTED`. Append-only; never canonical. | Low — simple file append | **YES** | **NO** |

---

## 2. Deferred from MVP (Phase 1 or P1)

| # | Capability | Rationale | Dependency Risk | Required for MVP Release |
|---|---|---|---|---|
| 1 | **Slack ingress** | Adds Bolt dependency, webhook infra, OAuth, rate limits. CLI is sufficient for proving the core loop. Slack is a P1 polish layer. | High — external service setup | NO |
| 2 | **Full AI-Q Research Node** | The AI-Q Blueprint adapter (intent classifier → shallow/deep research → citations) is valuable but not required to prove NIM routing works. A basic `planning_node` that calls NIM directly is sufficient for MVP. | High — needs external repo integration | NO |
| 3 | **Qdrant RAG** | Vector DB adds container, indexing pipeline, chunking strategy, embedding model management. MVP can load knowledge from `wiki/` and `memory/long_term/` as flat Markdown files into prompt context. RAG is P1 optimization. | High — new infrastructure | NO |
| 4 | **CrewAI multi-squad execution** | CrewAI remains in MVP but constrained to **single crew per job**. Multi-squad coordination (coding + research + review simultaneously) adds debugging complexity without proving the core NIM router thesis. | Medium — already used, just constrained | NO |
| 5 | **NIM embedding/rerank APIs** | Depends on Qdrant (deferred). No value without vector search pipeline. | High — blocked by Qdrant | NO |
| 6 | **NIM safety/PII guard models** | Important for production but MVP runs in trusted local environment with HITL gates. Basic regex secret scan in `audit.py` is sufficient for MVP. | Medium — needs NIM safety model access | NO |
| 7 | **Data Flywheel evaluation loop** | Requirements explicitly exclude full rollout. JSONL logging is in MVP; the feedback/evaluation/retraining loop is Phase 2. | High — needs eval harness design | NO |
| 8 | **LangGraph checkpoint-based job resume** | Automatic resume of a job from `SqliteSaver` checkpoint after daemon crash. MVP recovery path: daemon rebuilds state, detects `EXECUTING` job with no checkpoint → transitions to `FAILED`. Manual operator may clone to new JOB. Checkpoint saving is IN (see #14); automatic resume from checkpoint is P1. | Medium — needs LangGraph checkpoint introspection | NO |
| 9 | **Prometheus/Grafana observability** | JSONL logs are sufficient for MVP. Dashboards are operational polish. | High — new infrastructure | NO |
| 10 | **Brev / cloud GPU validation** | MVP-A is local Docker Compose only. Cloud validation is Phase 2. | High — cloud accounts + GPU | NO |
| 11 | **Kubernetes / Helm manifests** | Future scaling path. MVP runs on single machine (WSL2). | High — not needed locally | NO |
| 12 | **Full `run_job.ps1` → `wiki_daemon` migration** | `run_job.ps1` stays as L2 adapter until daemon is fully verified. Remove only after 10 successful end-to-end jobs. | Low — migration risk | NO |

---

## 3. Rejected for MVP (Explicitly Out)

| # | Capability | Rationale | Risk If Included |
|---|---|---|---|
| 1 | **Cloud delegation / auto-scaling** | U-01 explicitly Phase 4+. No trigger conditions defined. Adding this now would create undecidable routing logic. | Architecture drift, undefined behavior |
| 2 | **Wiki auto-promotion** | Violates HITL Gate 3 invariant. No automated path from `audit PASS` to `wiki/`. Brain must review every promotion. | Knowledge pollution, security breach |
| 3 | **Self-hosted NIM containers** | MVP prioritizes Hosted NIM API. Self-hosted adds Docker GPU runtime, model download, TensorRT-LLM complexity. | Scope explosion, GPU resource conflict with Ollama |
| 4 | **ChatDev 2.0 adoption** | U-03: No stable branch confirmed. Design consultation only. No LangGraph integration established. | Dependency on unstable upstream |
| 5 | **GitHub Copilot CLI router integration** | U-02: REST API existence unconfirmed. Isolate as Antigravity tool if needed later. | Undecidable interface |
| 6 | **Dynamic crew / agent generation** | CrewAI roles are statically defined in config. No runtime agent creation. Prevents unbounded execution trees. | Debugging complexity, cost explosion |
| 7 | **Recursive job spawning** | A JOB may not create another JOB. Prevents infinite chains and resource exhaustion. | Runaway execution, billing risk |
| 8 | **Auto-merge to main branch** | HITL Gate 2 must approve every merge. No automated git merge, ever, in MVP. | Production safety violation |
| 9 | **Multi-tenant SaaS features** | RBAC beyond owner/operator is out. Single-user/small-team only. | Identity/auth complexity |
| 10 | **Fine-tuning / LoRA training** | Data Flywheel Phase 2+. MVP saves logs only. No model customization. | ML pipeline infrastructure |

---

## 4. Scope Change Rules (Post-Freeze)

1. **Nothing from Deferred may enter MVP without replacing an equal-complexity In item.**
2. **Nothing from Rejected may enter MVP without CEO approval and ADR revision.**
3. **If an In item is discovered to be infeasible, it may be demoted to Deferred with a technical reason recorded in `adr/ADR-XXX-scope-change.md`.**
4. **MVP success is defined as: CLI → JOB → daemon → LangGraph → NIM router → artifact → audit → HITL → promote → Hermes. If any In item blocks this, it is a P0 bug, not a scope expansion.**

---

## 5. Dependency Chain for MVP Execution

```
Block A (Foundation — Week 1)
  ├─ Create apps/daemon/, apps/llm_router/
  ├─ routing_config.yaml (canonical)
  ├─ .env.example (NVIDIA_API_KEY + NIM_API_KEY fallback)
  └─ `nim_router.py`, `complexity_scorer.py` placement

Block B (Orchestration — Week 2)
  ├─ Minimal wiki_daemon (watchdog + status transitions)
  ├─ LangGraph graph.py with 3 nodes: load_job → router_node → execute
  ├─ HITL Gate 1 (interrupt)
  └─ SQLite checkpoint persistence confirmed (save only; auto-resume is P1)

Block C (Router + Providers — Week 2-3)
  ├─ llm_router.py 4-line NIM patch
  ├─ Kimi provider adapter
  ├─ router_node integration (complexity_scorer → llm_router)
  └─ Ollama fallback verified

Block D (Execution + Audit — Week 3-4)
  ├─ CrewAI single-crew execution node
  ├─ audit.py lightweight gate
  ├─ HITL Gate 2
  └─ Artifact capture

Block E (Knowledge — Week 4-5)
  ├─ HITL Gate 3
  ├─ promote.py (raw → wiki)
  ├─ hermes_reflect.py
  └─ JSONL logging confirmed
```

**Critical path:** Block A → Block C → Block D → Block E. Block B can parallelize with C.

---

*Frozen by: Chief MVP Architect*
*Date: 2026-04-24*
*Next review: After first end-to-end job execution or upon CEO request.*
