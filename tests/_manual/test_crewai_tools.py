import sys
from pathlib import Path

# Ensure project root is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from crewai_tools import FileReadTool

def test_file_read_tool():
    # Create a temp file to read
    temp_file = Path("test_read.txt")
    temp_file.write_text("Hello from crewai-tools", encoding="utf-8")
    
    try:
        tool = FileReadTool(file_path=str(temp_file))
        result = tool._run()
        print(f"Result: {result}")
        assert "Hello" in result
        print("PASS: FileReadTool works")
    finally:
        if temp_file.exists():
            temp_file.unlink()

if __name__ == "__main__":
    test_file_read_tool()
