# Antigravity MVP — Release Notes

## Version 1.1.0 — Phase B: L1 Knowledge OS + Domains

### New Features

#### Domain-Aware Knowledge Management (B-001 ~ B-005)
- **3 knowledge domains**: `game/`, `market/`, `personal/`
  - Each domain has `raw/` (ingestion) and `wiki/` (canonical) subdirectories
  - Per-domain `.domain` metadata files define allowed squads
- **Karpathy 4-Operation Model** (`domains/knowledge_os.py`):
  - `save(domain, topic, content)` — Atomic write with YAML frontmatter
  - `load(domain, topic)` — Read with frontmatter stripping (`load_body()`)
  - `search(domain, query)` — Vector search (agentmemory) or fallback grep
  - `derive(src, dst, query)` — **Audited cross-domain synthesis** (only cross-domain op)
- **Squad Permission Enforcement**: Squads can only access domains listed in `.domain` `allowed_squads`
- **Cross-Domain Leak Prevention**: `derive()` is the only way to move knowledge between domains; all calls logged to `work/blackboard/cross_domain_audit.jsonl`

#### Domain-Aware Promotion (B-003)
- `promote.py --domain <game|market|personal>` routes artifacts to correct domain wiki
- Backward compatible: omit `--domain` to use `work/wiki/` (MVP 1.0 behavior)

#### Cross-Domain Audit Script (B-004)
- `scripts/cross_domain_audit.py` — Detect unauthorized cross-domain references
- Checks: leakage patterns, squad permissions, derive() audit trail completeness
- Usage: `--domain`, `--trail`, `--json` flags

#### Domain-Aware Graph Orchestration (B-006)
- `graph.py` reads `domain:` from JOB YAML frontmatter
- `squad_router` node filters squads by domain permissions
- Squad objectives auto-prefixed with `[Domain: X]` context

#### Updated JOB Spec (B-007)
- New `domain:` field in YAML frontmatter (`game` | `market` | `personal`)
- Optional `squads:` override for ad-hoc squad composition
- Full backward compatibility with MVP 1.0.0 JOB files

### Test Results

```
tests/test_domain_isolation.py — 17 passed, 0 failed

Coverage:
  ✓ B-001: Domain directory structure
  ✓ B-002: Karpathy 4-op model (save/load/search/derive)
  ✓ B-003: Squad permission enforcement
  ✓ B-004: Cross-domain leakage prevention
  ✓ B-005: Fallback search (vector search when agentmemory available)
  ✓ Integration: Full E2E workflow
```

### Files Added/Modified

```
domains/
├── __init__.py              # KnowledgeOS exports
├── knowledge_os.py          # Core 4-op implementation (+227 lines)
├── README.md                # Domain structure documentation
├── game/.domain             # Domain metadata
├── market/.domain
├── personal/.domain
scripts/
├── promote.py               # Added --domain, --topic, --squad params
├── cross_domain_audit.py    # NEW: Leakage detection script
├── audit.py                 # Secret scan + syntax + scope guard
├── cancel.py                # Job cancellation
├── approve.py               # HITL Gate 1/2/3
├── hermes_reflect.py        # Wiki → vector index (domain-aware)
├── scope_guard.py           # Forbidden import detection
├── init_project.py          # L0 workspace scaffolding
apps/runtime/
├── graph.py                 # Domain-aware squad routing
apps/daemon/
├── wiki_daemon.py           # File watchdog + atomic locking
apps/llm_router/
├── router.py                # NIM + Ollama unified router
docs/
├── JOB_SPEC.md              # Phase B domain-aware JOB specification
tests/
└── test_domain_isolation.py # 17 automated tests
```

### Architecture Progress

| Layer | MVP 1.0.0 | Phase B (1.1.0) |
|-------|-----------|-----------------|
| L0 Workspace Scaffold | ✅ init_project.py | ✅ + domains/ |
| L1 Knowledge OS | ❌ | ✅ Karpathy 4-op + domain isolation |
| L2 Brain↔Developer | ❌ | 🔄 blackboard/ ready |
| L3 Execution Runtime | ✅ graph.py | ✅ + domain routing |
| Slack Ingress | ✅ Socket Mode | ✅ (unchanged) |
| LLM Router | ✅ NIM + Ollama | ✅ (unchanged) |
| HITL Gates | ✅ 1/2/3 CLI | ✅ (unchanged) |

### Next: Phase C — L2 Brain↔Developer Separation

- `work/blackboard/` protocol for Brain review state
- Squad execution → blackboard checkpoint → human review → continue

---

## Version 1.0.0 — Phase 1 MVP (Previous Release)

See git log for full MVP 1.0.0 details. Key components:
- LangGraph orchestrator with SQLite checkpointing
- CrewAI multi-squads (coding/research/review)
- Unified LLM router (NIM + Ollama)
- HITL Gates 1/2/3
- Atomic file I/O + stale-lock reclaim
- Slack Socket Mode ingress
- 14 automated regression tests (all passing)
