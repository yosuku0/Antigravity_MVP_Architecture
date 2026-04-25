# Import Manifest — Third-Party Repository Integration

## e2b-dev/e2b
- **Cloned to:** `vendor/e2b/`
- **License:** Apache-2.0
- **Integrated into:** `apps/runtime/sandbox_executor.py`
- **Purpose:** Safe code execution in sandbox
- **API Key Required:** `E2B_API_KEY` (free tier available at e2b.dev)
- **Build-vs-Import decision:** Import — e2b specializes in sandbox infra, building from scratch would take weeks
- **Integration complexity:** LOW (pip install + API key)

## browser-use/browser-use
- **Cloned to:** `vendor/browser-use/`
- **License:** MIT
- **Integrated into:** `apps/crew/squads/research_squad/tools/browser_tool.py`
- **Purpose:** Web research for Research Squad
- **API Key Required:** None (uses local browser)
- **Build-vs-Import decision:** Import — browser automation is complex
- **Integration complexity:** MEDIUM (Selenium/Playwright dependencies)

## run-llama/liteparse
- **Cloned to:** `vendor/liteparse/`
- **License:** MIT
- **Integrated into:** `scripts/ingest.py`
- **Purpose:** `raw/` → structured format for `wiki/`
- **API Key Required:** None
- **Build-vs-Import decision:** Import — document parsing is complex
- **Integration complexity:** MEDIUM (chunking logic adaptation)

## modelcontextprotocol/servers
- **Cloned to:** `vendor/mcp-servers/`
- **License:** MIT
- **Integrated into:** `apps/tools/mcp_registry.py`
- **Purpose:** MCP tool protocol for external tool integration
- **API Key Required:** None
- **Build-vs-Import decision:** Import — protocol implementation is complex
- **Integration complexity:** HIGH (MCP client/server architecture)

## rohitg00/agentmemory
- **Cloned to:** `vendor/agentmemory/`
- **License:** MIT
- **Integrated into:** `scripts/hermes_reflect.py` enhancement
- **Purpose:** Structured agent memory management
- **API Key Required:** None
- **Build-vs-Import decision:** Import — memory indexing/search is complex
- **Integration complexity:** MEDIUM (data structure adaptation)

## crewAIInc/crewAI-tools
- **Cloned to:** `vendor/crewai-tools/`
- **License:** MIT
- **Integrated into:** `apps/crew/squads/*/tools/`
- **Purpose:** Pre-built tools for all squads
- **API Key Required:** Varies by tool
- **Build-vs-Import decision:** Import — tool ecosystem is large
- **Integration complexity:** LOW (already CrewAI-compatible)
