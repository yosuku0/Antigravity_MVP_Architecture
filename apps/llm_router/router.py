# apps/llm_router/router.py
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)

from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama

class ProviderBudgetExhausted(Exception):
    pass

class LLMRouter:
    """Unified router for NIM, Ollama, and paid providers."""
    
    def __init__(self):
        self.nvidia_api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY")
        if not self.nvidia_api_key:
            raise EnvironmentError(
                "NVIDIA_API_KEY not set. Copy .env.example to .env and fill in your key."
            )
        self._switch_count = 0
        self._max_switches = 2
    
    def get_llm(self, context: str):
        """Return a LangChain LLM instance for the given routing context."""
        
        if context in ("nim_fast", "nim_cheap", "classify_remote"):
            # NIM: meta/llama-3.1-8b-instruct (fast/cheap)
            return ChatOpenAI(
                openai_api_base="https://integrate.api.nvidia.com/v1",
                openai_api_key=self.nvidia_api_key,
                model_name="meta/llama-3.1-8b-instruct",
                temperature=0.7,
                max_tokens=512,
            )
        
        elif context in ("nim_large", "nim_code", "review"):
            # NIM: meta/llama-3.3-70b-instruct (large)
            return ChatOpenAI(
                openai_api_base="https://integrate.api.nvidia.com/v1",
                openai_api_key=self.nvidia_api_key,
                model_name="meta/llama-3.3-70b-instruct",
                temperature=0.5,
                max_tokens=1024,
            )
        
        elif context == "classify_local":
            # Ollama: qwen2.5:7b
            return Ollama(
                model="qwen2.5:7b",
                base_url="http://localhost:11434",
            )
        
        elif context == "exploration":
            # Kimi (placeholder — will be implemented in C-005)
            raise NotImplementedError("Kimi provider not yet implemented (C-005)")
        
        else:
            # Default fallback: Ollama
            return Ollama(
                model="qwen2.5:7b",
                base_url="http://localhost:11434",
            )
    
    def chat(self, context: str, messages: list, max_retries: int = None) -> str:
        """Chat with automatic fallback on failure."""
        if max_retries is None:
            max_retries = self._max_switches
        
        if self._switch_count >= self._max_switches:
            raise ProviderBudgetExhausted(
                f"Provider switch budget exhausted ({self._max_switches} switches)"
            )
        
        llm = self.get_llm(context)
        try:
            res = llm.invoke(messages)
            if hasattr(res, "content"):
                return res.content
            return str(res)
        except Exception as e:
            self._switch_count += 1
            if self._switch_count >= self._max_switches:
                raise ProviderBudgetExhausted(
                    f"Provider switch budget exhausted after {self._switch_count} switches"
                ) from e
            
            # Fallback to Ollama
            print(f"[router] Fallback to Ollama (switch {self._switch_count}/{self._max_switches}) due to error: {e}")
            return self.chat("classify_local", messages, max_retries - 1)

if __name__ == "__main__":
    # Quick test
    try:
        router = LLMRouter()
        print("NIM LLM:", router.get_llm("nim_fast"))
        print("Ollama LLM:", router.get_llm("classify_local"))
    except Exception as e:
        print(f"Error initializing router: {e}")
