import sys
import shutil
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from apps.runtime.graph import run_job
from utils.atomic_io import write_frontmatter

def test_reject_loop_flow(tmp_path, monkeypatch):
    # Setup mock project structure in tmp_path
    jobs_dir = tmp_path / "work" / "jobs"
    jobs_dir.mkdir(parents=True)
    (tmp_path / "work" / "artifacts" / "staging").mkdir(parents=True)
    (tmp_path / "domains" / "game").mkdir(parents=True)
    (tmp_path / "domains" / "game" / ".domain").write_text("allowed_squads: [coding_squad]", encoding="utf-8")
    
    monkeypatch.chdir(tmp_path)
    
    job_id = "REJECT-TEST-001"
    job_path = jobs_dir / f"{job_id}.md"
    
    # 1. Create Initial Job
    initial_content = "---\ndomain: game\n---\nWrite a hello world script."
    job_path.write_text(initial_content, encoding="utf-8")
    
    print("=== Step 1: Initial Run (to audit) ===")
    res1 = run_job(str(job_path))
    print(f"Status after run 1: {res1['status']}")
    
    # 2. Manually Reject
    print("\n=== Step 2: Manually Rejecting via CLI ===")
    from scripts.approve import approve_gate_2
    approve_gate_2(job_path, "operator", reject=True, reason="Please add more comments.")
    
    # Verify job file state
    text = job_path.read_text(encoding="utf-8")
    print(f"Job file after reject:\n{text}")
    assert "gate_2_rejected" in text
    assert "Please add more comments." in text

    # 3. Resume Run (Rejection Loop)
    print("\n=== Step 3: Resuming (should detect rejection and re-plan) ===")
    
    # We can't easily intercept the internal state, but we can check the final objective
    # In this test, the graph will loop: load_job -> plan_executor -> run_executor -> brain_review
    # brain_review will fail again (Artifact too short), so the final objective in res2
    # will contain the LATEST feedback.
    
    res2 = run_job(str(job_path))
    print(f"Status after run 2: {res2['status']}")
    # The final objective will have the LATEST feedback from brain_review loop
    print(f"Final objective contains 'Artifact too short': {'Artifact too short' in res2.get('planned_objective')}")
    print(f"Final objective contains 'Please add more comments.': {'Please add more comments.' in res2.get('planned_objective')}")
    
    # Check if the recovered feedback was used at least once
    # Since plan_executor is called first, we can check if it's there
    # Wait, the objective is updated on each loop.
    
    assert "Please add more comments." in res2.get("planned_objective")
    print("\nReject-Loop verification SUCCESS!")

if __name__ == "__main__":
    import pytest
    # Simple manual execution if run directly
    from unittest.mock import MagicMock
    class TmpPath:
        def __init__(self, path): self.path = path
        def __truediv__(self, other): return TmpPath(self.path / other)
        def mkdir(self, **k): self.path.mkdir(**k)
        def write_text(self, t, **k): self.path.write_text(t, **k)
        def read_text(self, **k): return self.path.read_text(**k)
        def exists(self): return self.path.exists()
        def __str__(self): return str(self.path)
    
    # Just use pytest style with a real temp dir if needed, but run_command is better
    pass
