import os
import sys
import subprocess
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
wiki_dir = repo_root / "wiki_test"
hermes_file = repo_root / "runtime" / "hermes" / "memory_test.md"
reflect_script = repo_root / "scripts" / "hermes_reflect.py"

def test_hermes():
    success = True
    print("Testing Hermes reflection...")
    
    # 1. Create dummy wiki files
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "f1.md").write_text("content 1", encoding="utf-8")
    
    # 2. Run hermes_reflect.py
    print("Running reflection...")
    subprocess.run([sys.executable, str(reflect_script), "--wiki-dir", "wiki_test", "--hermes", "runtime/hermes/memory_test.md"], check=True)
    
    # 3. Assert memory.md exists and contains entries
    if not hermes_file.exists():
        print("FAIL: memory_test.md not created.")
        success = False
    else:
        content = hermes_file.read_text(encoding="utf-8")
        if "f1.md" not in content:
            print("FAIL: f1.md not found in memory.")
            success = False
        else:
            print("PASS: f1.md found in memory.")

    # 4. Run again → assert append
    (wiki_dir / "f2.md").write_text("content 2", encoding="utf-8")
    print("Running reflection again...")
    subprocess.run([sys.executable, str(reflect_script), "--wiki-dir", "wiki_test", "--hermes", "runtime/hermes/memory_test.md"], check=True)
    
    content = hermes_file.read_text(encoding="utf-8")
    if "f2.md" not in content:
        print("FAIL: f2.md not found in memory after append.")
        success = False
    if content.count("## Reflection") < 2:
        print("FAIL: Did not find multiple reflection headers.")
        success = False
    else:
        print("PASS: Multiple reflections found.")

    # Cleanup
    import shutil
    if wiki_dir.exists(): shutil.rmtree(wiki_dir)
    if hermes_file.exists(): hermes_file.unlink()
    
    if success:
        print("D-003 TEST PASSED")
        exit(0)
    else:
        print("D-003 TEST FAILED")
        exit(1)

if __name__ == "__main__":
    test_hermes()
