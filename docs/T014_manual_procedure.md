# T014: End-to-End Manual Verification Procedure

This document outlines the manual verification steps for the NIM-Kinetic Meta-Agent MVP.

## Prerequisites
- [ ] Python 3.12 installed and `py -3.12` available.
- [ ] Ollama running locally with `qwen2.5:7b`.
- [ ] `.env` file containing `NVIDIA_API_KEY`.
- [ ] All dependencies installed: `pip install -r requirements.txt`.

## Step 1: Start the Daemon
1. Open a terminal.
2. Run: `py -3.12 apps/daemon/wiki_daemon.py`
3. Verify output shows "WikiDaemon started...".

## Step 2: Create a Job (Ingress)
1. In another terminal, run a script or manually create `work/jobs/JOB-001.md`:
   ```markdown
   ---
   job_id: JOB-001
   status: created
   objective: "Implement a Python script that calculates Fibonacci numbers."
   ---
   # JOB-001
   ```
2. Verify: The daemon should NOT pick it up yet (status remains `created`).

## Step 3: HITL Gate 1 (Approval)
1. Run: `py -3.12 scripts/approve.py --job work/jobs/JOB-001.md --gate 1`
2. Verify: The daemon console should show "CLAIMED JOB-001" and then "EXECUTING JOB-001".

## Step 4: Execution & Audit
1. Wait for execution to finish.
2. Check `work/jobs/JOB-001.md`. Status should become `audit_passed`.
3. Check `memory/working/JOB-001/artifact.py`. It should contain the Fibonacci code.

## Step 5: HITL Gate 2 (Artifact Approval)
1. Run: `py -3.12 scripts/approve.py --job work/jobs/JOB-001.md --gate 2`
2. Verify: Status becomes `approved_gate_2`.

## Step 6: Promotion (Stage)
1. Run: `py -3.12 scripts/promote.py --job work/jobs/JOB-001.md --mode stage`
2. Verify: Status becomes `promotion_pending`. Check `work/artifacts/staging/JOB-001/` for files.

## Step 7: HITL Gate 3 (Promotion Approval)
1. Run: `py -3.12 scripts/approve.py --job work/jobs/JOB-001.md --gate 3`
2. Verify: Status becomes `approved_gate_3`.

## Step 8: Final Promotion & Reflection
1. Run: `py -3.12 scripts/promote.py --job work/jobs/JOB-001.md --mode execute`
2. Verify:
   - Status becomes `promoted`.
   - Files appear in `wiki/`.
   - `runtime/hermes/memory.md` is updated with the reflection.

## Step 9: Cleanup
1. Stop the daemon (Ctrl+C).
2. Clean up test files if necessary.
