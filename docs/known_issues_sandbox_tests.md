# Resolved: Sandbox Stability Test Failures

The previously identified failures in the sandbox execution tier tests have been resolved in the `fix/sandbox-stability-tests` branch.

**Resolves #2**

## Status: RESOLVED

- `tests/test_sandbox.py::test_tier_2_local_execution` -> **RESOLVED** (Updated to `test_tier_2_docker_execution`)
- `tests/test_sandbox.py::test_tier_3_fallback` -> **RESOLVED** (Implemented Tier 3 Local venv fallback and updated test verification)

## Fix Details

### 1. Tier 2 Alignment
- Renamed the test to `test_tier_2_docker_execution` to match the implementation that uses Docker for Tier 2.
- Updated mocks to target `_check_docker_readiness` and `run_in_docker`.

### 2. Tier 3 Implementation
- Restored the missing Tier 3 "Local venv" fallback in `apps/runtime/sandbox_executor.py` using `utils.safe_subprocess`.
- Added a safety note regarding lower isolation in local venv compared to Docker/e2b.
- Split `test_tier_3_fallback` into two targeted tests:
    - `test_tier_3_local_venv_execution`: Verifies successful fallback to local venv when e2b and Docker fail.
    - `test_all_tiers_fail_skip`: Verifies the final "Skip" state when all execution tiers (including local venv) fail.

## Verification

The entire test suite (`pytest tests/`) is now 100% green.
- `tests/test_sandbox.py`: 4/4 PASSED
- `tests/test_promotion_state_machine.py`: 28/28 PASSED
- Total: 79 PASSED
