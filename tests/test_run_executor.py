import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from apps.runtime.nodes.run_executor import run_executor

@pytest.fixture
def base_state():
    return {
        "job_id": "TEST-JOB",
        "squads": ["coding_squad", "research_squad"],
        "target_domain": "game",
        "planned_objective": "Test objective",
        "parallel": False,
        "status": "executing",
        "review_count": 0,
    }

def test_sequential_execution(base_state, tmp_path, monkeypatch):
    """逐次実行モード（デフォルト）が正しく動作する"""
    # staging_dir を tmp_path に向ける
    staging_dir = tmp_path / "work/artifacts/staging"
    staging_dir.mkdir(parents=True)
    
    # run_executor 内部の staging_dir をパッチするか、CWD を変更
    monkeypatch.chdir(tmp_path)
    
    with patch("apps.runtime.nodes.run_executor.execute_squad") as mock_exec:
        mock_exec.side_effect = lambda name, llm, obj, path, domain: {"result": f"Result from {name}"}
        
        state = base_state.copy()
        result = run_executor(state)
        
        assert result["status"] == "reviewing"
        assert result["artifact_path"].exists()
        content = result["artifact_path"].read_text(encoding="utf-8")
        assert "### coding_squad" in content
        assert "### research_squad" in content
        assert content.index("coding_squad") < content.index("research_squad")
        assert mock_exec.call_count == 2

def test_parallel_execution(base_state, tmp_path, monkeypatch):
    """並列実行モードが正しく動作する"""
    staging_dir = tmp_path / "work/artifacts/staging"
    staging_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    
    with patch("apps.runtime.nodes.run_executor.execute_squad") as mock_exec:
        # 遅延を入れて完了順序をバラバラにする
        import time
        def slow_exec(name, *args, **kwargs):
            if name == "coding_squad":
                time.sleep(0.1)
            return {"result": f"Result from {name}"}
        
        mock_exec.side_effect = slow_exec
        
        state = base_state.copy()
        state["parallel"] = True
        result = run_executor(state)
        
        assert result["status"] == "reviewing"
        assert result["artifact_path"].exists()
        content = result["artifact_path"].read_text(encoding="utf-8")
        
        # 順序が維持されているか確認
        assert "### coding_squad" in content
        assert "### research_squad" in content
        assert content.index("coding_squad") < content.index("research_squad")

def test_parallel_artifact_isolation(base_state, tmp_path, monkeypatch):
    """並列実行時に各 squad の一時ファイルが独立している"""
    staging_dir = tmp_path / "work/artifacts/staging"
    staging_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    
    with patch("apps.runtime.nodes.run_executor.execute_squad") as mock_exec:
        def mock_side_effect(name, llm, obj, path, domain):
            path.write_text(f"Result from {name}", encoding="utf-8")
            return {"result": f"Result from {name}"}
            
        mock_exec.side_effect = mock_side_effect
        
        state = base_state.copy()
        state["parallel"] = True
        result = run_executor(state)
        
        # 一時ファイルが作成されているか確認
        assert (staging_dir / "TEST-JOB_coding_squad.md").exists()
        assert (staging_dir / "TEST-JOB_research_squad.md").exists()
        assert (staging_dir / "TEST-JOB.md").exists()
