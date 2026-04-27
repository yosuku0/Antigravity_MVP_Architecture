> **Historical example — not an active JOB**
>
> This file is retained as a historical implementation request/example.
> It is not an active runtime JOB and must not be executed from `work/jobs/`.
> Current Gate 1/2/3 lifecycle and metadata are defined by:
> - \doc/job_lifecycle_spec.md> - \docs/JOB_SPEC.md> - \doc/adr/ADR-001-mvp-control-plane.md>
> Do not use this file as an implementation source without checking the current lifecycle specs.

---
job_id: SAMPLE-001
target_domain: game
squads:
  - coding_squad
---

# Sample Objective
Implement a simple hello world in Python and save it to `hello.py`.
Verify that it prints "Hello World".
