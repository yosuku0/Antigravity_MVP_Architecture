"""
router.py — Unified LLM Router: NIM + Ollama coexistence

Usage:
    router = UnifiedRouter()
    llm = router.get_llm("nim_fast")      # NIM for speed
    llm = router.get_llm("nim_cheap")     # NIM cost-optimized
    llm = router.get_llm("classify_local") # Ollama for privacy

Provider-switch budget:
    - Max 2 switches per job, then FAILED
    - Track usage in model_calls.jsonl
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

# CrewAI LLM (our preferred wrapper)
try:
    from crewai import LLM
    CREWAI_LLM_AVAILABLE = True
except ImportError:
    CREWAI_LLM_AVAILABLE = False
    LLM = None

from utils.atomic_io import atomic_append


import threading

# Singleton management
_router_instance = None
_router_lock = threading.RLock()


class ProviderExhaustedError(Exception):
    """Raised when provider-switch budget is exceeded."""
    pass


class UnifiedRouter:
    """Routes LLM calls between NIM (cloud) and Ollama (local).

    Key implementation detail:
      Uses crewai.LLM with openai/ prefix for NIM to avoid 401 errors.
      This sends requests through OpenAI-compatible endpoint at
      https://integrate.api.nvidia.com/v1 with proper auth.
    """

    MAX_SWITCHES = 2

    def __new__(cls, *args, **kwargs):
        global _router_instance
        if _router_instance is None:
            with _router_lock:
                if _router_instance is None:
                    _router_instance = super().__new__(cls)
        return _router_instance

    def __init__(self, log_path: str = "work/model_calls.jsonl") -> None:
        with _router_lock:
            if getattr(self, "_initialized", False):
                return

            self.nvidia_api_key = os.environ.get("NVIDIA_API_KEY", "")
            self.ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            self.log_path = Path(log_path)
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._switch_count = 0
            self._state_lock = threading.RLock()

            self._initialized = True

    def get_llm(self, context: str):
        """Get appropriate LLM for the given context.

        Contexts:
            nim_fast      → NIM Llama 3.1 8B (fast inference)
            nim_cheap     → NIM Llama 3.1 8B (cost-optimized)
            classify_local → Ollama qwen2.5:7b (local, private)
            code_local    → Ollama qwen2.5-coder:7b (local coding)
        """
        if not CREWAI_LLM_AVAILABLE:
            raise RuntimeError("CrewAI not installed — cannot create LLM")

        if context in ("nim_fast", "nim_cheap"):
            if not self.nvidia_api_key:
                raise RuntimeError("NVIDIA_API_KEY not set")
            llm = LLM(
                model='openai/meta/llama-3.1-8b-instruct',
                base_url='https://integrate.api.nvidia.com/v1',
                api_key=self.nvidia_api_key,
            )
            self._log_call("nvidia_nim", "meta/llama-3.1-8b-instruct", context)
            return llm

        elif context == "classify_local":
            llm = LLM(model='ollama/qwen2.5:7b', base_url=self.ollama_base_url)
            self._log_call("ollama", "qwen2.5:7b", context)
            return llm

        elif context == "code_local":
            llm = LLM(model='ollama/qwen2.5-coder:7b', base_url=self.ollama_base_url)
            self._log_call("ollama", "qwen2.5-coder:7b", context)
            return llm

        else:
            # Default: try NIM, fallback to Ollama
            if self.nvidia_api_key:
                return self.get_llm("nim_fast")
            return self.get_llm("classify_local")

    def switch_provider(self) -> str:
        """Switch provider (counts toward MAX_SWITCHES budget).

        Returns:
            Name of new provider

        Raises:
            ProviderExhaustedError: if budget exceeded
        """
        with self._state_lock:
            if self._switch_count >= self.MAX_SWITCHES:
                raise ProviderExhaustedError(
                    f"Provider-switch budget exceeded ({self.MAX_SWITCHES} max)"
                )
            self._switch_count += 1
            count = self._switch_count
            self._log_call("system", "provider_switch", f"switch_{count}")
            return "ollama" if count % 2 == 1 else "nvidia_nim"

    def _log_call(self, provider: str, model: str, context: str) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "provider": provider,
            "model": model,
            "context": context,
        }
        atomic_append(self.log_path, json.dumps(entry, ensure_ascii=False))


def get_router() -> UnifiedRouter:
    """Helper to get the singleton UnifiedRouter instance."""
    return UnifiedRouter()
