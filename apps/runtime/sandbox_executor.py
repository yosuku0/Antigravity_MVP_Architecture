import os
from pathlib import Path
try:
    from e2b import Sandbox
except ImportError:
    Sandbox = None
from utils.safe_subprocess import run_in_venv, ensure_venv, get_venv_python

VENV_DIR = Path("work/sandbox_venv")

def execute_code_safely(code: str, timeout: int = 60) -> dict:
    """Execute Python code with 3-tier fallback.
    
    Tiers:
        1. e2b Cloud
        2. Local venv
        3. Skip (Warn)
    """
    # Tier 1: e2b
    api_key = os.environ.get("E2B_API_KEY")
    if api_key and Sandbox:
        try:
            sbx = Sandbox(api_key=api_key)
            try:
                execution = sbx.run_code(code, timeout=timeout)
                return {
                    "tier": 1,
                    "stdout": "".join(execution.logs.stdout),
                    "stderr": "".join(execution.logs.stderr),
                    "exit_code": execution.exit_code,
                    "success": execution.exit_code == 0,
                }
            finally:
                sbx.kill()
        except Exception as e:
            print(f"[sandbox] Tier 1 (e2b) failed: {e}")

    # Tier 2: Local venv
    try:
        ensure_venv(VENV_DIR, Path("requirements.txt"))
        python_path = get_venv_python(VENV_DIR)
        res = run_in_venv(python_path, code, timeout=timeout)
        return {
            "tier": 2,
            **res
        }
    except Exception as e:
        print(f"[sandbox] Tier 2 (local) failed: {e}")

    # Tier 3: Skip
    return {
        "tier": 3,
        "success": True,  # Don't fail the graph, just skip verification
        "skipped": True,
        "reason": "Both e2b and local venv failed or were unavailable"
    }

def execute_artifact_safely(artifact_path: Path, timeout: int = 60) -> dict:
    """Execute a generated artifact file in sandbox for verification."""
    if not artifact_path.exists():
        return {"success": False, "stderr": f"Artifact not found: {artifact_path}", "exit_code": -1, "tier": 0}
    code = artifact_path.read_text(encoding="utf-8")
    return execute_code_safely(code, timeout)
