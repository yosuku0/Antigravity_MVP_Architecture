# NIM-Kinetic Meta-Agent — Integration Architecture v1.0

> **Status note — historical architecture gap analysis**
>
> This document is retained as a historical integration/gap-analysis reference. It is not the current execution plan.
> Current HITL / promotion invariants are defined by:
> - `docs/architecture/requirements_canonical.md`
> - `doc/job_lifecycle_spec.md`
> - `doc/adr/ADR-001-mvp-control-plane.md`
> - `docs/JOB_SPEC.md`
>
> Do not start the roadmap items in this document without a new approved task, PR plan, and validation plan.
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
| **Brain# Antigravity Phase G Requirements: Scaling & Self-Evolution

## 1. 目的
Phase F までに完成した「堅牢な実行基盤」をベースに、運用のスケーラビリティ（量）と、ナレッジの質的な進化（質）を両立させる機能を実装します。

## 2. 主要機能要件

### [G1] インタラクティブ HITL (Slack Integration)
ターミナルに縛られず、モバイルや Slack 経由でジョブを監視・承認・拒否できる環境を構築します。

- **技術設計アプローチ**:
    - **Slack Bolt (Python) の導入**: `apps/daemon/slack_adapter.py` を新設し、**Gate 2** の承認・拒否通知を Slack に送信。Slack は **Gate 2** のみ対応し、**Gate 3** は CLI のみです。
    - **インタラクティブボタン**: Slack 上の Approve/Reject ボタンから `scripts/approve.py` 相当のロジックを呼び出す。
    - **非同期状態管理**: Slack からの入力を JOB ファイルに反映し、`wiki_daemon` が次回のスキャンで検知して処理を再開。
    - **Slack は wiki への書き込み権限を持たず、canonical wiki コンテンツは `promote.py --mode execute`（CLI）でのみ更新されます。

### [G2] 並列ジョブスケジューリング & リソース管理
多数のジョブを効率的に処理するための並列実行エンジンを構築します。

- **技術設計アプローチ**:
    - **ジョブキュー・マネージャー**: `wiki_daemon` を拡張し、`RUNNABLE` なジョブを複数のワーカープロセス（またはスレッド）に割り当て。
    - **Docker リソース制限**: 各ジョブを実行するコンテナに CPU/メモリの制限（例: `--cpus 1 --memory 512m`）を動的に設定し、ホストのリソース枯渇を防止。
    - **分散ロック (Locking)**: 複数のワーカーが同一のジョブや出力先を同時に編集しないよう、`work/locks` 下に原子的なディレクトリ/ファイルベースのロック機構を実装。

### [G3] 継続的ナレッジ合成 (Continuous Synthesis)
拒否理由や実行エラーを「筋肉」として蓄積し、AI の精度を自律的に向上させます。in LangGraph

```mermaid
Entry → Load JOB
→ [Gate 1] HITL
→ Router (classify → select squad)
→ Squad Execution (sequential for MVP):
    → Research Squad (if research needed)
    → Coding Squad (implementation)
    → Review Squad (audit + security)
→ [Gate 2] HITL (Slack/CLI approval)
→ approved_gate_2 → `promote.py --mode stage`
→ promotion_pending
→ [Gate 3] HITL (CLI only)
→ approved_gate_3 → `promote.py --mode execute`
→ promoted
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

## 5. Historical Next Task Candidate

The previous next-task candidate was Multi-Squad Implementation. It remains a future candidate only and must not be executed without a new approved task, fresh design review, and explicit validation plan.
