#!/usr/bin/env python3
"""Unified LLM router for NIM, Ollama, and paid providers."""
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# NIM native endpoint
try:
    from langchain_nvidia_ai_endpoints import ChatNVIDIA
    NVIDIA_ENDPOINTS_AVAILABLE = True
except ImportError:
    NVIDIA_ENDPOINTS_AVAILABLE = False

# Ollama
from langchain_community.llms import Ollama

class LLMRouter:
    def __init__(self):
        self.nvidia_api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY")
    
    def get_llm(self, context: str):
        """Return a LangChain LLM instance for the given routing context."""
        
        if context in ("nim_fast", "nim_cheap", "classify_remote"):
            if not NVIDIA_ENDPOINTS_AVAILABLE:
                raise RuntimeError("langchain-nvidia-ai-endpoints not installed")
            if not self.nvidia_api_key:
                raise EnvironmentError("NVIDIA_API_KEY not set")
            return ChatNVIDIA(
                model="meta/llama-3.1-8b-instruct",
                api_key=self.nvidia_api_key,
                temperature=0.7,
                max_tokens=512,
            )
        
        elif context in ("nim_large", "nim_code", "review"):
            if not NVIDIA_ENDPOINTS_AVAILABLE:
                raise RuntimeError("langchain-nvidia-ai-endpoints not installed")
            if not self.nvidia_api_key:
                raise EnvironmentError("NVIDIA_API_KEY not set")
            return ChatNVIDIA(
                model="meta/llama-3.3-70b-instruct",
                api_key=self.nvidia_api_key,
                temperature=0.5,
                max_tokens=1024,
            )
        
        elif context == "classify_local":
            return Ollama(
                model="qwen2.5:7b",
                base_url="http://localhost:11434",
            )
        
        elif context == "exploration":
            # Kimi placeholder or fallback to NIM
            return self.get_llm("nim_fast")
        
        else:
            return Ollama(model="qwen2.5:7b", base_url="http://localhost:11434")
    
    def chat(self, context: str, messages: list, max_retries: int = 2) -> str:
        llm = self.get_llm(context)
        try:
            # chat() should return content as string for backward compatibility
            from langchain_core.messages import HumanMessage, SystemMessage
            lc_messages = []
            for m in messages:
                if m["role"] == "system":
                    lc_messages.append(SystemMessage(content=m["content"]))
                else:
                    lc_messages.append(HumanMessage(content=m["content"]))
            
            res = llm.invoke(lc_messages)
            if hasattr(res, "content"):
                return res.content
            return str(res)
        except Exception as e:
            if max_retries > 0 and not context.startswith("classify_local"):
                print(f"Router fallback due to: {e}")
                return self.chat("classify_local", messages, max_retries - 1)
            raise

if __name__ == "__main__":
    router = LLMRouter()
    print("NIM LLM:", router.get_llm("nim_fast"))
    print("Ollama LLM:", router.get_llm("classify_local"))
