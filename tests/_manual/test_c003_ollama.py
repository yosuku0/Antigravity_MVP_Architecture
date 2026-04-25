import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.append(str(repo_root))

from apps.llm_router.router import LLMRouter

def test_ollama_connectivity():
    print("Testing Ollama connectivity through router...")
    try:
        router = LLMRouter()
        response = router.chat('classify_local', [{'role': 'user', 'content': 'Say exactly "Ollama OK"'}])
        print(f"Response: {response}")
        
        if "Ollama OK" in response:
            print("C-003 TEST PASSED")
            exit(0)
        else:
            print("FAIL: Response did not contain 'Ollama OK'.")
            exit(1)
    except Exception as e:
        print(f"FAIL: Exception during Ollama test: {e}")
        exit(1)

if __name__ == "__main__":
    test_ollama_connectivity()
