# Lessons Learned - Phase E Completion

## Architecture & Graph
- **Node Completeness**: When refactoring a graph (e.g., separating `run_executor`), ensure all nodes like `audit` or `promote` remain correctly aliased (`audit_node = audit`) and defined within `graph.py` or imported explicitly.
- **State SSOT**: The JOB file's frontmatter is the ultimate ground truth for status. The daemon and orchestrator must reconcile their internal state with the file's frontmatter at every step.

## Security & Sandbox
- **Fail-Closed Execution**: Sandbox skips (Tier 3) must explicitly return `success: False`. Allowing skips to count as success leads to "false positive" paths where unverified code is promoted.
- **Secret Scanning**: Centralize sensitive patterns (OpenAI/NVIDIA keys) in a single module (e.g., `scripts/audit.py`) and import them into the runtime graph to ensure consistency between manual audits and automated runtime checks.

## Reliability & I/O
- **Log Integrity**: For JSONL logging, `atomic_append` must guarantee a trailing newline. Without it, concurrent or sequential appends can merge lines, breaking log parsers.
- **Venv Resilience**: On Windows, always check for Python/pip readiness in the venv before execution, as library installations can partially fail or locks can remain.

## Workflow & HITL
- **Status Gating**: The daemon should strictly filter runnable jobs (e.g., `approved_gate_1`). Jobs in `created` or `queued` status without explicit approval should be skipped with a clear log entry.
- **CLI Feedback**: Tools like `approve.py` must perform the actual state change in the filesystem, not just log the action, to ensure the next component (daemon) sees the update.
