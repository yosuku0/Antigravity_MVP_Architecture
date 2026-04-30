# Maintenance Runbook

## Daily Checks

1. Run `python scripts/scope_guard.py .`.
2. Run `pytest -q tests`.
3. Inspect frozen jobs in `work/daemon_state.json`.
4. Review `work/daemon.jsonl` and `work/system.jsonl` for `ERROR` entries.

## Frozen Job Recovery

`wiki_daemon` freezes a JOB after `MAX_RETRIES` crash recoveries from `running`
back to a runnable state. The JOB frontmatter receives:

- `retry_count`
- `frozen: true`
- `freeze_reason`
- `frozen_at`

Human operator recovery:

1. Read the JOB file and latest daemon/system logs.
2. Fix the root cause or clone the JOB.
3. If retrying the same JOB is appropriate, clear `frozen`, clear
   `freeze_reason`, and set a deliberate `retry_count`.
4. Restart `python apps/daemon/wiki_daemon.py --once`.

## Log Rotation

`utils/logging_config.py` rotates `work/system.jsonl` at 10 MB with 5 retained
generations. Keep JSONL logs free of secrets and include `job_id` where possible.
