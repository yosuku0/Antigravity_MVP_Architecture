import os
import shutil
from pathlib import Path
from scripts.init_project import init_project

def test_a001_scaffold():
    test_project = "TestProject"
    # Use a local scratch directory instead of /tmp for Windows compatibility
    target_dir = Path(__file__).resolve().parents[2] / "scratch" / "test_scaffold"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        init_project(test_project, target_dir)
        
        project_path = target_dir / test_project
        assert (project_path / ".agent" / "context.md").exists(), "context.md missing"
        assert (project_path / ".agent" / "rules.md").exists(), "rules.md missing"
        assert (project_path / ".agent" / "memory.md").exists(), "memory.md missing"
        assert (project_path / "control-plane" / "constitutions" / "global.md").exists(), "global.md missing"
        
        print("A-001 Scaffold Test: PASSED")
    finally:
        # Cleanup
        if target_dir.exists():
            shutil.rmtree(target_dir)

if __name__ == "__main__":
    test_a001_scaffold()
