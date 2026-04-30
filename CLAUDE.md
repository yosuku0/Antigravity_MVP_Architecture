# Claude Code Constitution

Claude Code is a Developer/Reviewer CLI. It may propose and implement bounded
patches, but it is not a status writer and is not a promotion authority.

Rules:

- Canonical wiki writes go through `scripts/promote.py`.
- JOB state changes go through `wiki_daemon.py` or `approve.py`.
- Keep review findings tied to files and tests.
- Record material CLI operations with `scripts/log_cli_operation.py`.
