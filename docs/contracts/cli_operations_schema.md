# CLI Operations JSONL Schema

`logs/cli_operations.jsonl` records human-operated CLI activity. It is audit
evidence only; it does not grant write authority to any CLI.

Each JSONL row must include:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `ts` | string | yes | UTC ISO-8601 timestamp |
| `cli` | string | yes | Tool or wrapper name, e.g. `codex`, `gemini`, `promote.py` |
| `actor` | string | yes | Human/operator identity |
| `action` | string | yes | `read`, `write`, `edit`, `delete`, `promote`, `status_update`, etc. |
| `target_path` | string | yes | Workspace-relative path when possible |
| `outcome` | string | yes | `success`, `failed`, or `skipped` |
| `job_id` | string | no | Related JOB id |
| `detail` | string | no | Short diagnostic text; never include secrets |

Policy:

- Canonical wiki writes must go through `promote.py`.
- JOB status updates must go through `wiki_daemon.py` or `approve.py`.
- `.env*` files must not be written or captured through CLI operation logs.
- `scripts/scope_guard.py` validates this file when present.

Example:

```json
{"ts":"2026-04-30T00:00:00Z","cli":"codex","actor":"operator","action":"edit","target_path":"apps/runtime/graph.py","outcome":"success","job_id":"JOB-001","detail":"implementation patch"}
```
