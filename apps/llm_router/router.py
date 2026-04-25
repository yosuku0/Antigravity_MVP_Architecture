# apps/llm_router/router.py
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)

from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama

class LLMRouter:
    """Unified router for NIM, Ollama, and paid providers."""
    
    def __init__(self):
        self.nvidia_api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY")
        if not self.nvidia_api_key:
            raise EnvironmentError(
                "NVIDIA_API_KEY not set. Copy .env.example to .env and fill in your key."
            )
    
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
    
    def chat(self, context: str, messages: list, max_retries: int = 2) -> str:
        """Chat with automatic fallback on failure."""
        llm = self.get_llm(context)
        try:
            res = llm.invoke(messages)
            # Handle different return types (ChatOpenAI returns BaseMessage, Ollama returns str)
            if hasattr(res, "content"):
                return res.content
            return str(res)
        except Exception as e:
            if max_retries > 0 and not context.startswith("classify_local"):
                print(f"[router] Fallback to Ollama due to error: {e}")
                return self.chat("classify_local", messages, max_retries - 1)
            raise

if __name__ == "__main__":
    # Quick test
    try:
        router = LLMRouter()
        print("NIM LLM:", router.get_llm("nim_fast"))
        print("Ollama LLM:", router.get_llm("classify_local"))
    except Exception as e:
        print(f"Error initializing router: {e}")
