import pytest
import shutil
import os
from pathlib import Path
from apps.runtime.sandbox_executor import execute_code_safely

VENV_DIR_TEST = Path("work/sandbox_venv_test")

# Monkeypatch VENV_DIR in sandbox_executor
import apps.runtime.sandbox_executor
apps.runtime.sandbox_executor.VENV_DIR = VENV_DIR_TEST

def test_tier2_docker_ready(monkeypatch):
    """Tier 2 が Docker で動作することを検証"""
    # Force Tier 2 by clearing E2B_API_KEY
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    
    res = execute_code_safely("print('hello')")
    
    assert res["tier"] == 2
    assert res["success"] is True
    assert "hello" in res["stdout"]

def test_tier2_code_execution(monkeypatch):
    """Tier 2 で実際に Python コードが実行できるか検証"""
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    
    res = execute_code_safely("print('tier2_test')")
    
    assert res["tier"] == 2
    assert "tier2_test" in res["stdout"]
    assert res["success"] is True

def test_tier2_isolation(monkeypatch):
    """Tier 2 でホスト環境のパッケージにアクセスできないことを検証"""
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    
    # Host environment likely has pytest, but venv shouldn't (unless in requirements.txt)
    # Let's try a package that is definitely NOT in requirements.txt
    # requirements.txt currently has: crewai, langgraph, langchain, e2b, pyyaml, python-dotenv
    # Let's try importing 'requests' if it's not in requirements.txt (it's often a transitive dependency though)
    # Better: a random name like 'non_existent_package_123' or one that is in host but not in venv.
    
    # Actually, the user suggested "隔离の証拠" (Evidence of isolation).
    # I'll try to import 'black' or something common that I might have globally but not in requirements.txt.
    # Or just check if the venv is truly minimal.
    
    code = """
try:
    import black
    print('found')
except ImportError:
    print('not_found')
"""
    res = execute_code_safely(code)
    assert res["tier"] == 2
    assert "not_found" in res["stdout"]
