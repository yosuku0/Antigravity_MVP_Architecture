import os
from pathlib import Path
from scripts.ingest import ingest_file

def test_liteparse_ingest():
    repo_root = Path(__file__).resolve().parents[2]
    raw_dir = repo_root / "work" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = raw_dir / "test_knowledge.txt"
    test_file.write_text("This is a test knowledge base content.", encoding="utf-8")
    
    wiki_dir = repo_root / "wiki" / "test_ingest"
    
    success = ingest_file(test_file, wiki_dir)
    
    assert success, "Ingestion failed"
    output_file = wiki_dir / "test_knowledge.md"
    assert output_file.exists(), "Output file missing"
    assert "test knowledge" in output_file.read_text(encoding="utf-8").lower()
    
    print("PASS: Liteparse ingestion works")
    
    # Cleanup
    # if output_file.exists():
    #     output_file.unlink()
    # if test_file.exists():
    #     test_file.unlink()

if __name__ == "__main__":
    test_liteparse_ingest()
