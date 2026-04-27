# PR: Hardening HITL Promotion State Machine (P0 Fix)

## Summary

This PR addresses critical state machine integrity issues in the Antigravity MVP job lifecycle (P0). It ensures that job promotions, human-in-the-loop (HITL) gates, and daemon orchestration follow a strictly defined, one-way state machine that prevents unauthorized wiki writes and speculative state jumps.

### Key Changes
- **Graph Promotion Removal**: Modified `apps/runtime/graph.py` to stop at `audit_passed`. The Graph no longer has the authority to write to the final KnowledgeOS (wiki).
- **Hardened CLI Approval**: Refactored `scripts/approve.py` into a state-aware CLI that enforces prerequisite checks for Gate 2 (`audit_passed` required) and Gate 3 (`promotion_pending` required).
- **Slack Gate 2 Restriction**: Updated `apps/daemon/slack_adapter.py` to limit Slack approvals exclusively to Gate 2. Slack can no longer jump directly to `approved_gate_3`.
- **Decoupled Promotion Script**: Separated `scripts/promote.py` into `--mode stage` (artifact preparation) and `--mode execute` (final wiki write). Added strict hash verification to prevent artifact tampering between staging and execution.
- **Daemon Dispatcher Separation**: Refactored `apps/daemon/wiki_daemon.py` to separate Graph execution from promotion tasks. Promotion failures are now treated as non-terminal to allow for retries.
- **Regression Test Suite**: Added `tests/test_promotion_state_machine.py` providing 100% coverage of the new state machine, transition rules, and safety constraints.
- **Documentation Alignment**: Updated `README.md` and created a detailed `docs/walkthrough_p0_hitl_promotion.md` to reflect the current architecture.

## Test Results

- **Promotion Regression Suite**: `tests/test_promotion_state_machine.py` (35 tests) — **PASSED**
- **Audit & Promotion Logic**: `tests/test_audit_promote.py` — **PASSED**
- **HITL CLI Tests**: `tests/test_hitl.py` — **PASSED**
- **Daemon State Tests**: `tests/test_daemon.py` — **PASSED**
- **Full Suite Overview**: `pytest tests/ -q` — **76 passed, 2 failed** (see Known Issues).

## Known Non-blocking Failures

The following tests in `tests/test_sandbox.py` are currently failing:
1. `test_tier_2_local_execution`
2. `test_tier_3_fallback`

These failures existed prior to the P0 HITL Promotion fix (originating in commit `c67b905`) and are related to sandbox readiness checks. They are independent of the state machine logic addressed here and will be tracked in a separate issue.

## Security

- **Secret Grep**: Verified that no secrets are present in the codebase. Only placeholders in `.env.example` and documentation are present.
- **Public Repo Readiness**: All tests and documentation have been reviewed for sensitive information.

## Merge Notes

- **PR Review Mandatory**: Do not push directly to `main`. Use this document as the base for the GitHub PR description.
- **Sandbox Fix**: A follow-up PR should address the sandbox test failures identified in `docs/known_issues_sandbox_tests.md`.
