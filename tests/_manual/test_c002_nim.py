import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.append(str(repo_root))

from apps.llm_router.router import LLMRouter

def test_nim_connectivity():
    print("Testing NIM connectivity through router...")
    try:
        router = LLMRouter()
        # NIM: meta/llama-3.1-8b-instruct
        response = router.chat('nim_fast', [{'role': 'user', 'content': 'Say exactly "NIM OK"'}])
        print(f"Response: {response}")
        
        if "NIM OK" in response:
            print("C-002 TEST PASSED")
            exit(0)
        else:
            print("FAIL: Response did not contain 'NIM OK'.")
            exit(1)
    except Exception as e:
        print(f"FAIL: Exception during NIM test: {e}")
        exit(1)

if __name__ == "__main__":
    test_nim_connectivity()
