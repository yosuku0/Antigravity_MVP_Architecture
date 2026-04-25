import pytest
import tempfile
import shutil
from pathlib import Path
import yaml
from datetime import datetime, timezone

@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary repo structure for testing."""
    dirs = [
        "apps/daemon", "apps/llm_router/providers", "apps/runtime/nodes",
        "scripts", "tests", "work/jobs", "work/locks", "work/artifacts/staging",
        "memory/long_term", "memory/working", "runtime/hermes", "runtime/logs",
        "wiki", "raw"
    ]
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path

@pytest.fixture
def create_job(tmp_path):
    """Factory fixture to create a JOB file with given status."""
    def _create(job_id: str, status: str, **extra):
        job_path = tmp_path / "work" / "jobs" / f"{job_id}.md"
        job_path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter = {
            "job_id": job_id,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **extra
        }
        yaml_text = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
        content = f"---\n{yaml_text}---\n\n# {job_id}\n"
        job_path.write_text(content, encoding="utf-8")
        return job_path
    return _create

@pytest.fixture
def mock_nim_client(monkeypatch):
    """Mock NIM client for tests that don't need real API calls."""
    class MockLLM:
        def invoke(self, messages):
            class MockResponse:
                def __init__(self, content): self.content = content
            return MockResponse("Mock NIM response")
    monkeypatch.setattr("apps.llm_router.router.LLMRouter.get_llm", lambda self, ctx: MockLLM())
    return MockLLM()

@pytest.fixture
def mock_ollama_client(monkeypatch):
    """Mock Ollama client."""
    class MockLLM:
        def invoke(self, messages):
            return "Mock Ollama response"
    monkeypatch.setattr("apps.llm_router.router.LLMRouter.get_llm", lambda self, ctx: MockLLM())
    return MockLLM()
