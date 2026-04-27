# JOB File Specification — Phase B (Domain-Aware)

## Format

JOB files are Markdown with YAML frontmatter:

```yaml
---
job_id: JOB-20250425-001
type: coding | research | review
domain: game | market | personal  # NEW: target knowledge domain
squads:
  - coding_squad
  - research_squad  # Optional: override default squads
objective: |
  Clear description of the task
priority: P0 | P1 | P2
---

# Task Description

Full markdown body with context, requirements, references.
```

## Domain Field Semantics

| `domain` Value | Wiki Destination | Squad Filter | Vector Collection |
|----------------|------------------|--------------|-------------------|
| `game` | `domains/game/wiki/` | `.domain` `allowed_squads` | `domain_game` |
| `market` | `domains/market/wiki/` | `.domain` `allowed_squads` | `domain_market` |
| `personal` | `domains/personal/wiki/` | `.domain` `allowed_squads` | `domain_personal` |
| (omitted) | `work/wiki/` | All squads | (none) |

## Squad Override

If `squads` list is provided in frontmatter, it overrides the domain's
`.domain` `allowed_squads`. Use for ad-hoc squad composition.

## Example: Game Design Job

```yaml
---
job_id: JOB-GAME-001
type: coding
domain: game
objective: |
  Design a turn-based combat system with elemental weaknesses.
  Research existing systems in JRPGs for reference.
priority: P1
---

# Combat System Design

## Requirements
- 5 elements: Fire, Water, Earth, Wind, Void
- Each element strong against 2, weak against 2
- Combo system for chaining elemental reactions

## References
- Search domain:game for "combat" and "elemental"
- Derive from domain:market for "JRPG market trends"
```

## Backward Compatibility

Jobs WITHOUT `domain` field continue to use `work/wiki/` and all squads —
fully backward compatible with MVP 1.0.0.

## Runtime Metadata Fields

This section documents fields written to the JOB frontmatter by the system during execution. These fields enable self-observability and coordinate the HITL (Human-In-The-Loop) promotion lifecycle.

### 1. Core State

- `status`
    - The persisted lifecycle state of the job.
    - **Note**: Valid values and transitions are defined by [job_lifecycle_spec.md](../doc/job_lifecycle_spec.md). This document specifies field shape and usage, not the authoritative state machine.

### 2. Audit & Artifact Fields

- `audit_result`
    - Type: `string` (values: `pass` | `fail`)
    - Written by: `graph.py` (audit node) or standalone audit script.
    - Used by: `promote.py` as a prerequisite for staging.
- `audit_error`
    - Optional diagnostic string containing details about why an audit failed.
- `artifact_path`
    - Workspace-relative path to the generated artifact (e.g., `work/blackboard/JOB-ID.md`).
    - Used by: `slack_adapter.py` for notification and `promote.py` for staging.

### 3. HITL Approval Fields

The system tracks human approvals at three distinct gates.

- **Gate 1: Initial Execution**
    - `approved_by`: Name of the operator who authorized the initial graph run.
    - `approved_at`: ISO 8601 timestamp of authorization.
- **Gate 2: Promotion Staging**
    - `approved_gate_2_by`: Name of the reviewer (via CLI or Slack).
    - `approved_gate_2_at`: ISO 8601 timestamp.
- **Gate 3: Wiki Promotion (Execution)**
    - `approved_gate_3_by`: Name of the final authority (CLI only).
    - `approved_gate_3_at`: ISO 8601 timestamp.
    - **Requirement**: Gate 3 approval is strictly required before `promote.py --mode execute` will write to the canonical wiki.

### 4. Gate 2 Rejection Metadata

If a reviewer rejects a job at Gate 2, the following fields are recorded:

- `rejected_gate`: Integer (always `2` for Gate 2).
- `rejected_by`: Name of the person who rejected the request.
- `rejected_at`: ISO 8601 timestamp.
- `reject_reason`: Detailed feedback provided to the agents.
- **Note**: Gate 3 rejection is currently unsupported in the MVP; Gate 3 is a final execute/no-execute decision.

### 5. Slack Notification Metadata

- `slack_ts`
    - The unique timestamp (`ts`) of the Slack notification message.
    - Used to prevent duplicate Gate 2 notifications and to update the message thread with status changes.
    - **Note**: Slack is used for Gate 2 notifications, approvals, and rejections only; it cannot perform Gate 3.

### 6. Staging / Promotion Metadata

- `staged_artifact_path`
    - Path to the staged artifact under `work/artifacts/staging/JOB-###/`.
- `artifact_hash`
    - SHA-256 hash of the artifact generated during `stage`.
    - Used to verify integrity and prevent mid-approval tampering before `execute`.
- `staged_at`
    - Timestamp when `promote.py --mode stage` was successfully run.
- `promoted_at`
    - Timestamp of final wiki write.
- `promoted_hash`
    - Final integrity record of the promoted content.
- `promoted_path`
    - Final destination path in the canonical wiki (e.g., `domains/game/wiki/...`).
    - **Note**: Canonical wiki writes occur only during the `execute` phase.

### 7. Optional Trace Fields

- `gate_1_rejected_by`
    - An optional CLI trace field recorded if the initial authorization is rejected.
    - This is a diagnostic trace and not part of the primary promotion path.

### 8. Reserved / Lifecycle-spec Fields

The following fields are referenced by architectural specifications but are not currently written consistently by the runtime implementation:

- `failure_reason`: Diagnostic code for terminal failures (e.g., `provider_budget_exhausted`).
- `failure_node`: The specific graph node where the unrecoverable error occurred.

These fields are reserved for future schema synchronization and should not be treated as implemented runtime metadata.
