import pytest
import os
from apps.llm_router.router import LLMRouter, ProviderBudgetExhausted
from apps.llm_router.complexity_scorer import classify_task
from unittest.mock import MagicMock

def test_complexity_scorer():
    # Trivial
    res = classify_task("Just say hi")
    assert res["recommended_context"] == "classify_local"
    
    # Complex
    res = classify_task("Research AI trends in 2025")
    assert res["recommended_context"] == "nim_fast"
    
    # Code
    res = classify_task("Implement a fast sorting algorithm")
    assert res["recommended_context"] == "nim_fast"

def test_router_budget_exhaustion(monkeypatch):
    # Mock API Key to avoid EnvironmentError
    monkeypatch.setenv("NVIDIA_API_KEY", "mock")
    
    router = LLMRouter()
    router._max_switches = 1 # Force exhaustion on first fallback
    
    # Mock NIM to fail
    mock_fail = MagicMock()
    mock_fail.invoke.side_effect = Exception("NIM Fail")
    monkeypatch.setattr(router, "get_llm", lambda ctx: mock_fail)
    
    with pytest.raises(ProviderBudgetExhausted):
        router.chat("nim_fast", [{"role": "user", "content": "hi"}])

def test_router_fallback(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "mock")
    router = LLMRouter()
    router._max_switches = 2
    
    # Mock NIM to fail, but Ollama to succeed
    mock_nim = MagicMock()
    mock_nim.invoke.side_effect = Exception("NIM Fail")
    
    mock_ollama = MagicMock()
    mock_ollama.invoke.return_value = MagicMock(content="Ollama OK")
    
    def mock_get_llm(ctx):
        if ctx == "nim_fast": return mock_nim
        return mock_ollama
        
    monkeypatch.setattr(router, "get_llm", mock_get_llm)
    
    res = router.chat("nim_fast", [{"role": "user", "content": "hi"}])
    assert res == "Ollama OK"
    assert router._switch_count == 1
