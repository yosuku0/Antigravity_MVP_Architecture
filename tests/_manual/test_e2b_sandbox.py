#!/usr/bin/env python3
"""Test e2b sandbox execution."""
import os
import sys
from pathlib import Path

# Ensure project root is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps.runtime.sandbox_executor import execute_code_safely

def test_e2b_sandbox():
    result = execute_code_safely("print('hello from sandbox')")
    
    if result.get("skipped"):
        print(f"SKIP: {result['reason']}")
        return
    
    if not result["success"]:
        print(f"FAIL: Execution failed: {result['stderr']}")
        return

    assert "hello from sandbox" in result["stdout"]
    print("PASS: e2b sandbox execution works")

if __name__ == "__main__":
    test_e2b_sandbox()
