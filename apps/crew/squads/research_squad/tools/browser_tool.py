import asyncio
from crewai.tools import BaseTool
from browser_use import Agent, Browser
from langchain_openai import ChatOpenAI
import os

class WebResearchTool(BaseTool):
    name: str = "web_research"
    description: str = "Perform web research using a real browser. Useful for finding up-to-date information, stars on GitHub, or fact-checking."

    def _run(self, task: str) -> str:
        """Run the browser agent to perform research."""
        # Note: browser-use is async, so we need to run it in an event loop
        return asyncio.run(self._arun_research(task))

    async def _arun_research(self, task: str) -> str:
        # Use the same LLM as the router or a fast one
        # For browser-use, we need a vision-capable or high-quality model
        # We'll try to use the NVIDIA NIM key if available
        api_key = os.environ.get("NVIDIA_API_KEY")
        if api_key:
            llm = ChatOpenAI(
                model="meta/llama-3.1-8b-instruct",
                openai_api_key=api_key,
                openai_api_base="https://integrate.api.nvidia.com/v1"
            )
        else:
            # Fallback or error
            return "Error: NVIDIA_API_KEY required for high-quality web research."

        browser = Browser()
        agent = Agent(
            task=task,
            llm=llm,
            browser=browser
        )
        
        result = await agent.run()
        # Extract the final result from agent history or result
        return str(result)

if __name__ == "__main__":
    # Quick test
    tool = WebResearchTool()
    # res = tool._run("How many stars does crewai have on github?")
    # print(res)
