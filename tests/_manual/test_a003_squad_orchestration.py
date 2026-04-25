import os
import shutil
from pathlib import Path
import yaml
from apps.runtime.graph import app

def test_a003_squad_orchestration():
    job_id = "JOB-SQUAD-TEST"
    repo_root = Path(__file__).resolve().parents[2]
    job_path = repo_root / "work" / "jobs" / f"{job_id}.md"
    
    # 1. Create a JOB with routing_context = "nim_fast"
    # Note: router_node will overwrite routing_context based on objective,
    # so we set an objective that triggers nim_fast (level 2).
    # level 2 = nim_fast
    objective = "Implement a Python script to calculate Fibonacci numbers up to N."
    
    job_content = f"""---
job_id: {job_id}
status: approved_gate_1
objective: {objective}
---
"""
    job_path.write_text(job_content, encoding="utf-8")

    try:
        # 2. Run graph through squad_router and execute_squads
        # We need to mock the environment or ensure OLLAMA/NIM is available.
        # Since this is a manual test, we assume the environment is ready.
        
        inputs = {"job_path": str(job_path)}
        # We run it and check the state
        # Note: app.invoke returns the final state
        final_state = app.invoke(inputs)
        
        # 3. Assert state["squads"] contains expected squads
        # nim_fast triggers ["coding_squad", "review_squad"]
        assert "coding_squad" in final_state["squads"], "coding_squad missing"
        assert "review_squad" in final_state["squads"], "review_squad missing"
        
        # 5. Assert artifacts exist in memory/working/{job_id}/
        artifact_dir = repo_root / "memory" / "working" / job_id
        assert (artifact_dir / "coding_squad_artifact.py").exists(), "coding artifact missing"
        assert (artifact_dir / "review_squad_artifact.py").exists(), "review artifact missing"
        
        print("A-003 Squad Orchestration Test: PASSED")
        
    finally:
        # Cleanup
        if job_path.exists():
            job_path.unlink()
        # artifact_dir is useful for inspection, but we can clean it up for the test
        # shutil.rmtree(artifact_dir, ignore_errors=True)

if __name__ == "__main__":
    test_a003_squad_orchestration()
