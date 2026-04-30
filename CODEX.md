# Codex Constitution

Codex is a Developer CLI. It may edit code, tests, scripts, and documentation
inside the project scope.

Rules:

- Do not write canonical wiki files directly. Use `scripts/promote.py`.
- Do not update JOB status directly. Use `apps/daemon/wiki_daemon.py` or
  `scripts/approve.py`.
- Do not write secrets to JOB files, logs, artifacts, Hermes memory, or wiki.
- Record material CLI operations with `scripts/log_cli_operation.py`.
- Keep CrewAI inside LangGraph nodes; do not introduce a second orchestrator.
