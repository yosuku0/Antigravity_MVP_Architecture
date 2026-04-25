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
        """Return a string prefix (for CrewAI) or LLM instance for the given routing context."""
        
        # CrewAI 1.x / LiteLLM compatibility: Return string prefix for Agent.llm
        if context in ("nim_fast", "nim_cheap", "classify_remote"):
            return "nvidia_nim/meta/llama-3.1-8b-instruct"
        
        elif context in ("nim_large", "nim_code", "review"):
            return "nvidia_nim/meta/llama-3.3-70b-instruct"
        
        elif context == "classify_local":
            return "ollama/qwen2.5:7b"
        
        elif context == "exploration":
            # Kimi Open Platform (OpenAI-compatible via LiteLLM)
            kimi_key = os.environ.get("KIMI_API_KEY")
            if not kimi_key:
                return self.get_llm("nim_fast")
            return "moonshot/moonshot-v1-8k"
        
        else:
            return "ollama/qwen2.5:7b"
    
    def chat(self, context: str, messages: list, max_retries: int = None) -> str:
        """Chat using direct LangChain call with automatic fallback on failure."""
        if max_retries is None:
            max_retries = self._max_switches
        
        if self._switch_count >= self._max_switches:
            raise ProviderBudgetExhausted(
                f"Provider switch budget exhausted ({self._max_switches} switches)"
            )
        
        # For direct chat() calls, we use the real objects
        llm_type = self.get_llm(context)
        
        try:
            if llm_type.startswith("nvidia_nim/"):
                model = llm_type.split("/", 1)[1]
                llm = ChatOpenAI(
                    openai_api_base="https://integrate.api.nvidia.com/v1",
                    openai_api_key=self.nvidia_api_key,
                    model_name=model,
                    temperature=0.7,
                    max_tokens=512,
                )
            elif llm_type.startswith("ollama/"):
                model = llm_type.split("/", 1)[1]
                llm = Ollama(model=model, base_url="http://localhost:11434")
            elif llm_type.startswith("moonshot/"):
                model = llm_type.split("/", 1)[1]
                llm = ChatOpenAI(
                    openai_api_base="https://api.moonshot.cn/v1",
                    openai_api_key=os.environ.get("KIMI_API_KEY"),
                    model_name=model,
                    temperature=0.7,
                )
            else:
                llm = Ollama(model="qwen2.5:7b", base_url="http://localhost:11434")
                
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
        print("NIM LLM String:", router.get_llm("nim_fast"))
        print("Ollama LLM String:", router.get_llm("classify_local"))
    except Exception as e:
        print(f"Error initializing router: {e}")
