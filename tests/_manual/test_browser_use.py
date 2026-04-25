import os
import sys
from pathlib import Path

# Ensure project root is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps.crew.squads.research_squad.tools.browser_tool import WebResearchTool

def test_browser_use():
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        print("SKIP: NVIDIA_API_KEY not set")
        return
    
    tool = WebResearchTool()
    print("Running web research task...")
    result = tool._run("How many stars does crewAI have on GitHub?")
    
    print(f"Result: {result}")
    assert "stars" in result.lower() or "github" in result.lower()
    print("PASS: WebResearchTool works")

if __name__ == "__main__":
    test_browser_use()
