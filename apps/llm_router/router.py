#!/usr/bin/env python3
"""Unified LLM router for NIM, Ollama, and paid providers."""
import os
from pathlib import Path
from dotenv import load_dotenv
from crewai import LLM

env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Ollama
from langchain_community.llms import Ollama

class LLMRouter:
    def __init__(self):
        self.nvidia_api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY")
    
    def get_llm(self, context: str):
        """Return a crewai.LLM instance for the given routing context."""
        
        if context in ("nim_fast", "nim_cheap", "classify_remote"):
            if not self.nvidia_api_key:
                raise EnvironmentError("NVIDIA_API_KEY not set")
            # Use crewai.LLM with openai/ prefix to point to NIM endpoint
            # This is the most stable way to call NIM in crewai 1.x
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
            # For Ollama, we can still use the ollama/ prefix if crewai.LLM supports it
            # or return a LangChain Ollama object if crewai.LLM can wrap it.
            # Actually, crewai.LLM supports ollama/ directly.
            return LLM(
                model="ollama/qwen2.5:7b",
                base_url="http://localhost:11434",
            )
        
        elif context == "exploration":
            return self.get_llm("nim_fast")
        
        else:
            return LLM(model="ollama/qwen2.5:7b", base_url="http://localhost:11434")
    
    def chat(self, context: str, messages: list, max_retries: int = 2) -> str:
        llm = self.get_llm(context)
        try:
            # chat() should return content as string
            # crewai.LLM has a call method or similar? 
            # Actually, we can use it via a temporary Agent or just use LangChain for chat()
            
            # For chat(), let's use LangChain directly to avoid LLM wrapper overhead
            if context.startswith("nim") or context == "classify_remote":
                from langchain_openai import ChatOpenAI
                lc_llm = ChatOpenAI(
                    model="meta/llama-3.1-8b-instruct" if "fast" in context else "meta/llama-3.3-70b-instruct",
                    openai_api_key=self.nvidia_api_key,
                    openai_api_base="https://integrate.api.nvidia.com/v1"
                )
            else:
                lc_llm = Ollama(model="qwen2.5:7b", base_url="http://localhost:11434")
            
            from langchain_core.messages import HumanMessage, SystemMessage
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
            if max_retries > 0 and not context.startswith("classify_local"):
                print(f"Router fallback due to: {e}")
                return self.chat("classify_local", messages, max_retries - 1)
            raise

if __name__ == "__main__":
    router = LLMRouter()
    print("NIM LLM:", router.get_llm("nim_fast"))
    print("Ollama LLM:", router.get_llm("classify_local"))
