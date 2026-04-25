import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

repo_root = Path(__file__).resolve().parents[2]
sys.path.append(str(repo_root))

from apps.llm_router.router import LLMRouter, ProviderBudgetExhausted

def test_budget():
    success = True
    print("Testing provider-switch budget...")
    
    try:
        router = LLMRouter()
    except EnvironmentError:
        # If API key is missing, mock it for the test
        os.environ["NVIDIA_API_KEY"] = "mock_key"
        router = LLMRouter()
        
    router._max_switches = 2
    
    # 1. Mock get_llm to return a failing LLM for 'nim_fast'
    mock_fail_llm = MagicMock()
    mock_fail_llm.invoke.side_effect = Exception("Service Unavailable")
    
    # Mock Ollama too to be safe and fast
    mock_ollama_llm = MagicMock()
    mock_ollama_llm.invoke.return_value = MagicMock(content="Ollama Response")
    
    def mock_get_llm(context):
        if context == 'nim_fast':
            return mock_fail_llm
        return mock_ollama_llm
    
    router.get_llm = mock_get_llm
    
    # 2. First call: nim_fast fails -> fallback to Ollama (switch 1)
    print("First call (should fallback once)...")
    res = router.chat("nim_fast", [{"role": "user", "content": "hi"}])
    print(f"Response: {res}")
    if router._switch_count != 1:
        print(f"FAIL: Expected switch_count 1, got {router._switch_count}")
        success = False
    else:
        print("PASS: Fallback to Ollama occurred.")

    # 3. Second call: nim_fast fails -> switch 2 -> budget exhausted
    print("Second call (should exhaust budget)...")
    try:
        router.chat("nim_fast", [{"role": "user", "content": "hi"}])
        print("FAIL: Should have raised ProviderBudgetExhausted")
        success = False
    except ProviderBudgetExhausted as e:
        print(f"PASS: Raised ProviderBudgetExhausted as expected: {e}")
    except Exception as e:
        print(f"FAIL: Raised wrong exception: {type(e).__name__}: {e}")
        success = False

    if success:
        print("C-007 TEST PASSED")
        exit(0)
    else:
        print("C-007 TEST FAILED")
        exit(1)

if __name__ == "__main__":
    test_budget()
