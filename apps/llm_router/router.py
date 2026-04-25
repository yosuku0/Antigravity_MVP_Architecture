#!/usr/bin/env python3
"""Unified LLM router for NIM, Ollama, and paid providers."""
import os
from pathlib import Path
from dotenv import load_dotenv
from crewai import LLM

env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# LangChain / CrewAI imports for testing and logic
from langchain_community.llms import Ollama
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

class ProviderBudgetExhausted(Exception):
    """Raised when an LLM provider budget is exhausted (MVP stub)."""
    pass

class LLMRouter:
    def __init__(self):
        self.nvidia_api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY")
        self._switch_count = 0
        self._max_switches = 3
    
    def get_llm(self, context: str):
        """Return a crewai.LLM instance for the given routing context."""
        
        if context in ("nim_fast", "nim_cheap", "classify_remote"):
            if not self.nvidia_api_key:
                raise EnvironmentError("NVIDIA_API_KEY not set")
            return LLM(
                model="openai/meta/llama-3.1-8b-instruct",
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=self.nvidia_api_key,
                temperature=0.7,
                max_tokens=512,
            )
        
        elif context in ("nim_large", "nim_code", "review"):
            if not self.nvidia_api_key:
                raise EnvironmentError("NVIDIA_API_KEY not set")
            return LLM(
                model="openai/meta/llama-3.3-70b-instruct",
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=self.nvidia_api_key,
                temperature=0.5,
                max_tokens=1024,
            )
        
        elif context == "classify_local":
            return LLM(
                model="ollama/qwen2.5:7b",
                base_url="http://localhost:11434",
            )
        
        elif context == "exploration":
            return self.get_llm("nim_fast")
        
        else:
            return LLM(model="ollama/qwen2.5:7b", base_url="http://localhost:11434")
    
    def chat(self, context: str, messages: list, max_retries: int = 2) -> str:
        try:
            # For chat(), use LangChain directly
            if context.startswith("nim") or context == "classify_remote":
                lc_llm = ChatOpenAI(
                    model="meta/llama-3.1-8b-instruct" if "fast" in context else "meta/llama-3.3-70b-instruct",
                    openai_api_key=self.nvidia_api_key,
                    openai_api_base="https://integrate.api.nvidia.com/v1"
                )
            else:
                lc_llm = Ollama(model="qwen2.5:7b", base_url="http://localhost:11434")
            
            lc_messages = []
            for m in messages:
                if m["role"] == "system":
                    lc_messages.append(SystemMessage(content=m["content"]))
                else:
                    lc_messages.append(HumanMessage(content=m["content"]))
            
            res = lc_llm.invoke(lc_messages)
            if hasattr(res, "content"):
                return res.content
            return str(res)
        except Exception as e:
            self._switch_count += 1
            if self._switch_count >= self._max_switches:
                raise ProviderBudgetExhausted(f"Retry budget exhausted: {e}")
                
            if max_retries > 0 and not context.startswith("classify_local"):
                print(f"Router fallback due to: {e}")
                return self.chat("classify_local", messages, max_retries - 1)
            raise

if __name__ == "__main__":
    router = LLMRouter()
    print("NIM LLM:", router.get_llm("nim_fast"))
    print("Ollama LLM:", router.get_llm("classify_local"))
