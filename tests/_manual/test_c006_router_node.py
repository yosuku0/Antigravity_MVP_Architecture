import os
import sys
import yaml
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.append(str(repo_root))

from apps.llm_router.complexity_scorer import classify_task
from apps.runtime.graph import router_node

def test_router_node():
    success = True
    
    # 1. Test classify_task heuristics
    print("Testing classify_task heuristics...")
    # Based on implementation: 'implement' is in code_indicators -> nim_fast
    t1 = classify_task("Implement a hello world function")
    if t1["recommended_context"] != "nim_fast":
        print(f"FAIL: Expected nim_fast for 'implement', got {t1['recommended_context']}")
        success = False
    else:
        print("PASS: 'implement' -> nim_fast")
        
    t2 = classify_task("Just say hi")
    if t2["recommended_context"] != "classify_local":
        print(f"FAIL: Expected classify_local for trivial, got {t2['recommended_context']}")
        success = False
    else:
        print("PASS: trivial -> classify_local")

    # 2. Test router_node integration
    print("Testing router_node integration...")
    temp_job = repo_root / "work" / "jobs" / "JOB-C006.md"
    temp_job.parent.mkdir(parents=True, exist_ok=True)
    
    # 'Research' is in complex_indicators -> nim_fast
    temp_job.write_text("---\nobjective: Research AI trends\n---\nBody", encoding="utf-8")
    state = {"job_path": str(temp_job)}
    res = router_node(state)
    if res["routing_context"] != "nim_fast":
        print(f"FAIL: Expected nim_fast for research, got {res['routing_context']}")
        success = False
    else:
        print("PASS: research -> nim_fast in node")
        
    # Cleanup
    if temp_job.exists(): temp_job.unlink()
    
    if success:
        print("C-006 TEST PASSED")
        exit(0)
    else:
        print("C-006 TEST FAILED")
        exit(1)

if __name__ == "__main__":
    test_router_node()
