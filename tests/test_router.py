import pytest
import os
from apps.llm_router.router import LLMRouter, ProviderBudgetExhausted
from apps.llm_router.complexity_scorer import classify_task
from unittest.mock import MagicMock

def test_complexity_scorer():
    """C-006 verification: Task classification routes correctly."""
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
    """T013: Provider-switch retry budget exhaustion."""
    # Mock API Key to avoid EnvironmentError
    monkeypatch.setenv("NVIDIA_API_KEY", "mock")
    
    router = LLMRouter()
    router._max_switches = 1 # Force exhaustion on first fallback
    
    # Mock ChatOpenAI to fail
    mock_chat_openai = MagicMock()
    mock_instance = MagicMock()
    mock_instance.invoke.side_effect = Exception("NIM Fail")
    mock_chat_openai.return_value = mock_instance
    monkeypatch.setattr("apps.llm_router.router.ChatOpenAI", mock_chat_openai)
    
    with pytest.raises(ProviderBudgetExhausted):
        router.chat("nim_fast", [{"role": "user", "content": "hi"}])

def test_router_fallback(monkeypatch):
    """T004: Router fallback activation when NIM fails."""
    monkeypatch.setenv("NVIDIA_API_KEY", "mock")
    router = LLMRouter()
    router._max_switches = 2
    
    # Mock ChatOpenAI to fail
    mock_chat_openai = MagicMock()
    mock_instance = MagicMock()
    mock_instance.invoke.side_effect = Exception("NIM Fail")
    mock_chat_openai.return_value = mock_instance
    monkeypatch.setattr("apps.llm_router.router.ChatOpenAI", mock_chat_openai)
    
    # Mock Ollama to succeed
    mock_ollama = MagicMock()
    mock_ollama_instance = MagicMock()
    mock_ollama_instance.invoke.return_value = "Ollama OK"
    mock_ollama.return_value = mock_ollama_instance
    monkeypatch.setattr("apps.llm_router.router.Ollama", mock_ollama)
    
    # Ensure it starts with nim_fast
    res = router.chat("nim_fast", [{"role": "user", "content": "hi"}])
    assert res == "Ollama OK"
    assert router._switch_count == 1
