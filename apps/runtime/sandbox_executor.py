#!/usr/bin/env python3
"""Sandbox code execution using e2b."""
import os
from pathlib import Path
from e2b import Sandbox

def execute_code_safely(code: str, timeout: int = 60) -> dict:
    """Execute Python code in e2b sandbox.
    
    Returns:
        dict with keys: stdout, stderr, exit_code, success
    """
    api_key = os.environ.get("E2B_API_KEY")
    if not api_key:
        return {"skipped": True, "reason": "E2B_API_KEY not set"}
    
    try:
        sbx = Sandbox(api_key=api_key)
        try:
            execution = sbx.run_code(code, timeout=timeout)
            return {
                "stdout": "".join(execution.logs.stdout),
                "stderr": "".join(execution.logs.stderr),
                "exit_code": execution.exit_code,
                "success": execution.exit_code == 0,
            }
        finally:
            sbx.kill()
    except Exception as e:
        return {"success": False, "stderr": str(e), "exit_code": -1}

def execute_artifact_safely(artifact_path: Path, timeout: int = 60) -> dict:
    """Execute a generated artifact file in sandbox for verification."""
    if not artifact_path.exists():
        return {"success": False, "stderr": f"Artifact not found: {artifact_path}", "exit_code": -1}
    code = artifact_path.read_text(encoding="utf-8")
    return execute_code_safely(code, timeout)
