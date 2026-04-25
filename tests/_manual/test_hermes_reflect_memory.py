import os
import sys
from pathlib import Path

# Ensure project root is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.hermes_reflect import hermes_reflect

def test_hermes_reflect_memory():
    repo_root = Path(__file__).resolve().parents[2]
    wiki_dir = repo_root / "wiki" / "test_reflect"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    
    test_page = wiki_dir / "reflect_test.md"
    test_page.write_text("Knowledge about Antigravity system.", encoding="utf-8")
    
    hermes_path = repo_root / "runtime" / "hermes" / "test_memory.md"
    
    print("Running hermes_reflect...")
    hermes_reflect(wiki_dir, hermes_path)
    
    assert hermes_path.exists()
    assert "reflect_test.md" in hermes_path.read_text(encoding="utf-8")
    print("PASS: Hermes reflect with agentmemory indexing completed (check logs for success/skipped)")

if __name__ == "__main__":
    test_hermes_reflect_memory()
