import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from apps.runtime.sandbox_executor import execute_code_safely

def test_tier_1_e2b_mocked():
    """Verify that e2b is prioritized when API key is present."""
    with patch.dict("os.environ", {"E2B_API_KEY": "fake_key"}):
        with patch("apps.runtime.sandbox_executor.Sandbox") as MockSandbox:
            mock_sbx = MockSandbox.return_value
            mock_execution = MagicMock()
            mock_execution.logs.stdout = ["e2b output"]
            mock_execution.logs.stderr = []
            mock_execution.exit_code = 0
            mock_sbx.run_code.return_value = mock_execution
            
            code = "print('hello')"
            result = execute_code_safely(code)
            assert result["tier"] == 1
            assert "e2b output" in result["stdout"]

def test_tier_2_docker_execution():
    """Verify that Docker execution works when e2b is disabled."""
    with patch.dict("os.environ", {"E2B_API_KEY": ""}):
        with patch("apps.runtime.sandbox_executor._check_docker_readiness") as mock_ready:
            mock_ready.return_value = {"ready": True}
            with patch("utils.docker_executor.run_in_docker") as mock_run:
                mock_run.return_value = {
                    "stdout": "hello from docker",
                    "stderr": "",
                    "exit_code": 0,
                    "success": True
                }
                code = "print('hello from docker')"
                result = execute_code_safely(code)
                assert result["tier"] == 2
                assert "hello from docker" in result["stdout"]
                assert result["success"] is True
                mock_run.assert_called_once()

def test_tier_3_local_venv_execution():
    """Verify that local venv fallback works when Docker is unavailable."""
    with patch.dict("os.environ", {"E2B_API_KEY": ""}):
        # Mock Docker as unavailable
        with patch("apps.runtime.sandbox_executor._check_docker_readiness") as mock_ready:
            mock_ready.return_value = {"ready": False, "reason": "No docker"}
            
            with patch("apps.runtime.sandbox_executor.ensure_venv") as mock_ensure:
                with patch("apps.runtime.sandbox_executor.run_in_venv") as mock_run:
                    mock_run.return_value = {
                        "stdout": "hello from venv",
                        "stderr": "",
                        "exit_code": 0,
                        "success": True
                    }
                    code = "print('hello from venv')"
                    result = execute_code_safely(code)
                    
                    assert result["tier"] == 3
                    assert result["success"] is True
                    assert result["skipped"] is False
                    assert "hello from venv" in result["stdout"]
                    mock_ensure.assert_called_once()
                    mock_run.assert_called_once()

def test_all_tiers_fail_skip():
    """Verify fallback to skip state when all tiers fail."""
    with patch.dict("os.environ", {"E2B_API_KEY": ""}):
        # Mock Docker as unavailable
        with patch("apps.runtime.sandbox_executor._check_docker_readiness") as mock_ready:
            mock_ready.return_value = {"ready": False, "reason": "No docker"}
            
            # Mock local venv as failing
            with patch("apps.runtime.sandbox_executor.ensure_venv", side_effect=Exception("Venv setup failed")):
                code = "print('hello')"
                result = execute_code_safely(code)
                
                assert result["tier"] == 3
                assert result["skipped"] is True
                assert result["success"] is False
                assert result["verification_skipped"] is True
