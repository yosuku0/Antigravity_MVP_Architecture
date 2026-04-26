---
id: PHASE-D-001
status: pending
priority: high
context: coding
requires_hitl: true
---
# Objective
Implement Phase D: Brain↔Executor separation + coding_sandbox enhancement.

# Scope
1. Refactor `execute_squads` node in `apps/runtime/graph.py` into:
   - `plan_executor` node (Brain): objective construction, feedback injection, sandbox requirement detection
   - `run_executor` node (Executor): squad execution via `apps.crew.squad_executor`, artifact writing, sandbox verification

2. Strengthen `apps/runtime/sandbox_executor.py` with 3-tier fallback:
   - Tier 1: e2b cloud sandbox (existing)
   - Tier 2: local venv + subprocess (NEW — user confirmed venv is available)
   - Tier 3: skip with WARN log

3. Connect `squad_executor.execute_squad()` to the graph (currently graph falls back to placeholder).

# Acceptance Criteria
- [ ] `pytest tests/test_brain_loop.py tests/test_domain_isolation.py tests/test_hitl.py` = 24/24 PASSED
- [ ] `pytest tests/test_sandbox.py` = new tests PASSED
- [ ] `python scripts/scope_guard.py .` = no ERROR
- [ ] Feedback loop (brain_review → plan_executor → run_executor → brain_review) works for 3 iterations max
- [ ] sandbox_executor returns correct tier (1|2|3) in state
- [ ] No subprocess import in graph.py (direct import of review_artifact used instead)

# Artifacts
- `apps/runtime/nodes/plan_executor.py` (NEW)
- `apps/runtime/nodes/run_executor.py` (NEW)  
- `apps/runtime/sandbox_executor.py` (MODIFIED)
- `apps/runtime/graph.py` (MODIFIED)
- `tests/test_sandbox.py` (NEW)
- `tests/test_brain_loop.py` (MODIFIED)
