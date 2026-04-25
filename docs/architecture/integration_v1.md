# NIM-Kinetic Meta-Agent — Integration Architecture v1.0
## Synthesis of MVP 1.0.0 + P1-004 against Original 5-Layer Design

---

## 1. Executive Summary

The original vision (Integrated Design Document v1.0) defined a 5-layer meta-system:
- L0: Workspace Scaffold (`.agent/`, `global.md`, `TASK_SCHEMA`)
- L1: Knowledge OS (`raw→wiki`, domains/, audit, Hermes)
- L2: Coordination Daemon (wiki_daemon, Brain↔Developer blackboard)
- L3: Execution Runtime (LangGraph, CrewAI squads, LLM router, RAG, telemetry)
- Content Domain (game/market/personal from DIOGENES)

MVP 1.0.0 + P1-004 successfully implemented the minimal core loop:
- CLI/Slack ingress → JOB-###.md → daemon → LangGraph → NIM/Ollama → audit → HITL → promote → Hermes

This document defines the gap between MVP reality and full vision, and the path to close it.

---

## 2. Layer-by-Layer Gap Analysis

### L0: Workspace Scaffold — STATUS: NOT IMPLEMENTED (Gap: 100%)

| Original Design | MVP Reality | Gap | Priority |
|---|---|---|---|
| `.agent/` template directory with context loading order | Not present | Must create template | HIGH |
| `global.md` constitution (shared rules for all agents) | Not present | Must create | HIGH |
| `TASK_SCHEMA` alignment with JOB-###.md | Not present | Must create | MEDIUM |
| `<project>.md` per-project constitution override | Not present | Postponed | LOW |

**Implementation needed:**
- Create `.agent/` template with: `context.md`, `rules.md`, `memory.md` loading order
- Create `control-plane/constitutions/global.md` with: no production merge without CEO approval, no hardcoded secrets, HITL mandatory
- Create `scripts/init_project.py` that scaffolds new projects from template

---

### L1: Knowledge OS — STATUS: PARTIALLY IMPLEMENTED (Gap: ~60%)

| Original Design | MVP Reality | Gap | Priority |
|---|---|---|---|
| `raw/ → wiki/` promotion ritual | `promote.py` exists, basic | Add domain support | MEDIUM |
| `domains/` structure (agent-os-research, game, market, personal) | Not present | Must create | HIGH |
| Karpathy 4-operation model (Ingest/Compile/Query/Lint) | Not present | Design + implement | MEDIUM |
| Cross-domain audit (`audit.py` supports all domains) | Single domain only | Extend for domains | MEDIUM |
| `memory/long_term/` procedural memory | Not present | Create structure | LOW |
| `memory/decisions/` decision log | Not present | Create structure | LOW |

**Implementation needed:**
- Create `domains/` directory structure:
  ```
  domains/
    agent-os-research/
      raw/
      wiki/
    game/
      raw/
      wiki/
    market/
      raw/
      wiki/
    personal/
      raw/
      wiki/
  ```
- Update `promote.py` to accept `--domain` parameter
- Update `audit.py` for domain-specific rules

---

### L2: Coordination Daemon — STATUS: PARTIALLY IMPLEMENTED (Gap: ~50%)

| Original Design | MVP Reality | Gap | Priority |
|---|---|---|---|
| `wiki_daemon` with full state machine | Basic watchdog + lock | Add Brain↔Developer separation | HIGH |
| Brain↔Developer blackboard | Not present | Design blackboard protocol | HIGH |
| `run_job.ps1` as adapter to L2 | Not present | Create PowerShell adapter | LOW |
| Status ownership by daemon only | Implemented ✅ | — | — |

**Implementation needed:**
- Add Brain role detection in daemon: jobs with `source: brain` vs `source: developer`
- Create `work/blackboard/` for Brain↔Developer async communication
- Add `status: brain_review_pending` state for Brain-generated jobs

---

### L3: Execution Runtime — STATUS: PARTIALLY IMPLEMENTED (Gap: ~40%)

| Original Design | MVP Reality | Gap | Priority |
|---|---|---|---|
| LangGraph StateGraph with 4+ nodes | 4 nodes (load→router→execute→audit) | Add research_node, safety_node, merge_node | HIGH |
| CrewAI **squads** (coding + research + review, parallel) | Single crew (developer only) | Implement multi-squad | **HIGHEST** |
| LLM router with 5+ providers (Claude, Gemini, Kimi, OpenAI, Ollama, NIM) | NIM + Ollama + stubs | Activate Claude, Gemini, Kimi | MEDIUM |
| Qdrant RAG + NVIDIA embedding/rerank | Not present | Full implementation | MEDIUM |
| AI-Q Blueprint Research Node | Not present | Design simplified version | MEDIUM |
| Telemetry + Data Flywheel | JSONL logging only | Add evaluation loop | LOW |
| Budget management per job | Provider-switch cap only | Add cost/latency tracking | LOW |

**Implementation needed (HIGHEST priority = multi-squad):**
- Create `apps/crew/squads/` directory:
  ```
  squads/
    coding_squad/
      roles.yaml (developer, reviewer)
      tasks.yaml
    research_squad/
      roles.yaml (researcher, analyst)
      tasks.yaml
    review_squad/
      roles.yaml (auditor, security)
      tasks.yaml
  ```
- Update `graph.py` to run squads in sequence or parallel (MVP: sequential for safety)
- Add `squad_node` that instantiates correct squad based on `routing_context`

---

### Content Domain — STATUS: NOT IMPLEMENTED (Gap: 100%)

| Original Design | MVP Reality | Gap | Priority |
|---|---|---|---|
| DIOGENES game/market/personal content | Not present | Absorb content | LOW |
| `pal/agno` engine deprecation | Not applicable | Confirm no agno usage | LOW |

---

## 3. Multi-Agent Architecture Definition

The original design specified multiple agent types. MVP 1.0.0 collapsed them into a single `developer` agent. The multi-agent architecture must restore:

### Agent Types

| Agent | Role | Crew | LLM Context | Writes To |
|---|---|---|---|---|
| **Brain Agent** | Requirements, planning, JOB generation | N/A (human-like) | `planning` | `work/jobs/`, `memory/decisions/` |
| **Developer Agent** | Implementation, code generation | Coding Squad | `coding` / `nim_code` | `memory/working/`, source code |
| **Research Agent** | External research, citations | Research Squad | `research` / `aiq` | JOB Evidence section |
| **Review Agent** | Audit, security, quality | Review Squad | `review` | `audit_result`, review comments |
| **Classify Agent** | Task classification, routing | N/A | `classify_local` / `classify_remote` | `routing_context` |

### Multi-Agent Orchestration in LangGraph

```
Entry → Load JOB
→ [Gate 1] HITL
→ Router (classify → select squad)
→ Squad Execution (sequential for MVP):
    → Research Squad (if research needed)
    → Coding Squad (implementation)
    → Review Squad (audit + security)
→ [Gate 2] HITL
→ Merge / Promote
→ [Gate 3] HITL
→ Wiki Promotion
```

---

## 4. Implementation Roadmap (From Current State to Full Vision)

### Phase A: Multi-Squad + L0 Scaffold (Weeks 1-2)
1. Create `.agent/` template + `global.md`
2. Implement CrewAI squads (coding + research + review)
3. Update graph.py for squad orchestration
4. **Definition of Done:** A job can trigger research → code → review in sequence

### Phase B: L1 Knowledge OS + Domains (Weeks 3-4)
1. Create `domains/` structure
2. Update promote.py for `--domain`
3. Implement Karpathy 4-operation model (simplified)
4. **Definition of Done:** Multi-domain knowledge promotion works

### Phase C: L2 Brain↔Developer Separation (Weeks 5-6)
1. Create `work/blackboard/` protocol
2. Add Brain review state to daemon
3. Implement `run_job.ps1` adapter
4. **Definition of Done:** Brain-generated jobs go through review before execution

### Phase D: L3 Advanced Features (Weeks 7-10)
1. Qdrant RAG integration
2. AI-Q Research Node (simplified)
3. Activate all LLM providers (Claude, Gemini, Kimi)
4. Telemetry / Data Flywheel v1
5. **Definition of Done:** Full L3 capability as per original design

### Phase E: Integration Validation (Week 11-12)
1. End-to-end test across all layers
2. Performance benchmark
3. Documentation finalization

---

## 5. Immediate Next Task

**Start Phase A: Multi-Squad Implementation**

The first concrete task is to refactor `apps/crew/` from a single `config/` directory into a `squads/` structure with three squads, and update `graph.py` to orchestrate them.
