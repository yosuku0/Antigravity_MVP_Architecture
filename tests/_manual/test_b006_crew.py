import os
import sys
from pathlib import Path

# Ensure we can import app from apps.runtime.graph
repo_root = Path(__file__).resolve().parents[2]
sys.path.append(str(repo_root))

from apps.runtime.graph import app

# 1. Create a dummy JOB with a simple objective
jobs_dir = repo_root / "work" / "jobs"
jobs_dir.mkdir(parents=True, exist_ok=True)
job_path = jobs_dir / "JOB-TEST-006.md"
job_path.write_text("---\nstatus: approved_gate_1\nobjective: Implement a hello world function in Python\n---\nWrite a simple script that prints hello world.", encoding="utf-8")

# 2. Run graph.invoke() with initial_state
initial_state = {
    "job_path": str(job_path),
    "job_id": "",
    "status": "",
    "routing_context": "",
    "artifact_path": "",
    "audit_result": None,
    "crew_result": None
}

print("Invoking graph with CrewAI execution (this may take a minute)...")
try:
    final_state = app.invoke(initial_state)

    # Assertions
    success = True

    # 3. Assert artifact file exists
    if not final_state.get("artifact_path"):
        print("FAIL: artifact_path is missing from final state.")
        success = False
    else:
        artifact_path = Path(final_state["artifact_path"])
        if not artifact_path.exists():
            print(f"FAIL: artifact file not found at {artifact_path}")
            success = False
        else:
            print(f"PASS: artifact file exists at {artifact_path}")
            print("--- Artifact Content ---")
            print(artifact_path.read_text(encoding="utf-8"))
            print("------------------------")

    # 4. Assert audit_result
    if final_state.get("audit_result") != "pass":
        print(f"FAIL: audit_result is {final_state.get('audit_result')}, expected pass")
        success = False
    else:
        print("PASS: audit_result is pass.")

except Exception as e:
    print(f"FAIL: Graph execution failed: {e}")
    import traceback
    traceback.print_exc()
    success = False

# Cleanup
if job_path.exists(): job_path.unlink()

if success:
    print("B-006 TEST PASSED")
    exit(0)
else:
    print("B-006 TEST FAILED")
    exit(1)
