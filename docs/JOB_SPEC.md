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
