import os
import sys
from pathlib import Path

# Ensure we can import app from apps.runtime.graph
repo_root = Path(__file__).resolve().parents[2]
sys.path.append(str(repo_root))

from apps.runtime.graph import app

# 1. Create a dummy JOB with status: approved_gate_1
jobs_dir = repo_root / "work" / "jobs"
jobs_dir.mkdir(parents=True, exist_ok=True)
job_path = jobs_dir / "JOB-TEST-004.md"
job_path.write_text("---\nstatus: approved_gate_1\n---\nBody", encoding="utf-8")

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

print("Invoking graph...")
final_state = app.invoke(initial_state)

# Assertions
success = True

# 3. Assert status
if final_state["status"] != "approved_gate_1":
    print(f"FAIL: status is {final_state['status']}, expected approved_gate_1")
    success = False
else:
    print("PASS: status is correct.")

# 4. Assert routing_context
if final_state["routing_context"] != "classify_local":
    print(f"FAIL: routing_context is {final_state['routing_context']}, expected classify_local")
    success = False
else:
    print("PASS: routing_context is correct.")

# 5. Assert artifact file exists
artifact_path = Path(final_state["artifact_path"])
if not artifact_path.exists():
    print(f"FAIL: artifact file not found at {artifact_path}")
    success = False
else:
    print("PASS: artifact file exists.")

# 6. Assert audit_result
if final_state["audit_result"] != "pass":
    print(f"FAIL: audit_result is {final_state['audit_result']}, expected pass")
    success = False
else:
    print("PASS: audit_result is pass.")

# Cleanup
if job_path.exists(): job_path.unlink()
if artifact_path.exists(): artifact_path.unlink()

if success:
    print("B-004 TEST PASSED")
    exit(0)
else:
    print("B-004 TEST FAILED")
    exit(1)
