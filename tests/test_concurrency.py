import threading
import os
import json
import pytest
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch, mock_open

from domains.feedback_memory import get_feedback_memory, FeedbackMemory
from apps.llm_router.router import UnifiedRouter, get_router, ProviderExhaustedError
import domains.feedback_memory
import apps.llm_router.router

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test."""
    domains.feedback_memory._memory_instance = None
    apps.llm_router.router._router_instance = None
    yield

@patch("domains.feedback_memory.SentenceTransformer")
@patch("domains.feedback_memory.faiss")
def test_get_feedback_memory_concurrent_singleton(mock_faiss, mock_st):
    """Verify thread-safe singleton instantiation for FeedbackMemory."""
    mock_model = MagicMock()
    mock_st.return_value = mock_model
    
    mock_index = MagicMock()
    mock_faiss.IndexFlatIP.return_value = mock_index
    
    def get_instance():
        return get_feedback_memory()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        instances = list(executor.map(lambda _: get_instance(), range(10)))
    
    assert all(inst is instances[0] for inst in instances)
    assert mock_st.call_count == 1

@patch("domains.feedback_memory.SentenceTransformer")
@patch("domains.feedback_memory.faiss")
@patch("os.replace")
def test_feedback_memory_atomic_save_uses_temp_then_replace(mock_replace, mock_faiss, mock_st, tmp_path):
    """Verify _save uses temporary files and os.replace for atomicity."""
    memory = FeedbackMemory(storage_dir=tmp_path)
    memory._save()
    
    assert mock_faiss.write_index.called
    args, _ = mock_faiss.write_index.call_args
    assert str(args[1]).endswith(".index.tmp")
    mock_replace.assert_any_call(Path(args[1]), memory.index_path)
    
    found_meta_replace = False
    for call in mock_replace.call_args_list:
        if str(call[0][1]).endswith("lessons_meta.json"):
            found_meta_replace = True
            assert str(call[0][0]).endswith(".json.tmp")
    assert found_meta_replace

@patch("domains.feedback_memory.SentenceTransformer")
@patch("domains.feedback_memory.faiss")
def test_feedback_memory_concurrent_add_and_search_does_not_crash(mock_faiss, mock_st, tmp_path):
    """Verify concurrent add and search operations do not cause race conditions or crashes."""
    mock_model = MagicMock()
    mock_st.return_value = mock_model
    # Return a 384-dim vector for embeddings
    mock_model.encode.return_value = np.zeros((1, 384), dtype='float32')
    
    mock_index = MagicMock()
    mock_faiss.IndexFlatIP.return_value = mock_index
    mock_index.ntotal = 5
    # Mock search result: distances, indices
    mock_index.search.return_value = (np.array([[0.8]]), np.array([[0]]))
    
    memory = FeedbackMemory(storage_dir=tmp_path)
    # Pre-populate metadata to avoid index errors in search
    memory.metadata = [{"task": "t", "feedback": "f", "job_id": "j"}] * 10
    
    def worker_add():
        for i in range(20):
            memory.add_lesson(f"task {i}", "feedback", f"job-{i}")
            
    def worker_search():
        for i in range(20):
            memory.search_lessons(f"query {i}")
            
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for _ in range(4):
            futures.append(executor.submit(worker_add))
            futures.append(executor.submit(worker_search))
        
        for f in futures:
            f.result()
            
    assert len(memory.metadata) >= 80

def test_unified_router_singleton():
    """Verify UnifiedRouter construction returns a singleton instance."""
    with patch.dict(os.environ, {"NVIDIA_API_KEY": "mock"}):
        with patch("apps.llm_router.router.LLM"):
            def get_instance():
                return UnifiedRouter()
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                instances = list(executor.map(lambda _: get_instance(), range(10)))
            
            assert all(inst is instances[0] for inst in instances)
            assert get_router() is instances[0]

def test_unified_router_init_is_thread_safe():
    """Verify concurrent UnifiedRouter() calls do not expose partially initialized instances."""
    with patch.dict(os.environ, {"NVIDIA_API_KEY": "mock"}):
        with patch("apps.llm_router.router.LLM"):
            def get_instance():
                inst = UnifiedRouter()
                # If race occurs, fields might be missing or _initialized might be True prematurely
                assert hasattr(inst, "nvidia_api_key")
                assert hasattr(inst, "_state_lock")
                assert inst._initialized is True
                return inst

            with ThreadPoolExecutor(max_workers=10) as executor:
                instances = list(executor.map(lambda _: get_instance(), range(10)))
            
            assert all(inst is instances[0] for inst in instances)

def test_unified_router_switch_provider_budget_thread_safe():
    """Verify concurrent switch_provider() calls respect budget and are thread-safe."""
    with patch.dict(os.environ, {"NVIDIA_API_KEY": "mock"}):
        with patch("apps.llm_router.router.LLM"):
            router = UnifiedRouter()
            router._switch_count = 0
            router.MAX_SWITCHES = 50
            
            # Mock _log_call to avoid file I/O
            router._log_call = MagicMock()
            
            def worker_switch():
                successes = 0
                for _ in range(20):
                    try:
                        router.switch_provider()
                        successes += 1
                    except ProviderExhaustedError:
                        pass
                return successes

            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(lambda _: worker_switch(), range(10)))
            
            total_successes = sum(results)
            assert total_successes == 50
            assert router._switch_count == 50
            assert router._log_call.call_count == 50
