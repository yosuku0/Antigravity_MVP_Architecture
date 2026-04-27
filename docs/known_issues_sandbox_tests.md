# Known Issues: Sandbox Tests

This document tracks existing failures in the sandbox execution tier tests that are outside the scope of the P0 HITL Promotion fix.

## Affected Tests

- `tests/test_sandbox.py::test_tier_2_local_execution`
- `tests/test_sandbox.py::test_tier_3_fallback`

## Failure Details

### 1. `test_tier_2_local_execution`
- **Error**: `AttributeError: <module 'apps.runtime.sandbox_executor'> does not have the attribute '_check_tier2_readiness'`
- **Cause**: The test attempts to mock a function (`_check_tier2_readiness`) that either does not exist in the current version of `sandbox_executor.py` or was renamed/refactored.
- **Impact**: Tier 2 (Docker) readiness detection logic is not being correctly validated in this test.

### 2. `test_tier_3_fallback`
- **Error**: `AssertionError: assert 2 == 3`
- **Cause**: The test expects a fallback to Tier 3 (Local), but the executor stops at Tier 2 or returns a different tier level than expected.
- **Impact**: The 3-tier fallback logic needs synchronization between the implementation and the test expectations.

## History

These failures were first identified in the baseline prior to the HITL Promotion hardening (Commit `c67b905`). They do not affect the integrity of the job promotion state machine or the daemon's ability to dispatch jobs.

## Resolution Plan

1.  **Audit `apps/runtime/sandbox_executor.py`**: Confirm the current implementation of readiness checks.
2.  **Update `tests/test_sandbox.py`**: Align test mocks and assertions with the actual 3-tier logic.
3.  **Target**: Resolve in a follow-up PR focused on "Sandbox Stability".
