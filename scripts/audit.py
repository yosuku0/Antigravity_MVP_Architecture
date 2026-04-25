#!/usr/bin/env python3
"""Lightweight audit gate for MVP."""
import re
import sys
from pathlib import Path

# Simple secret patterns (MVP scope)
SECRET_PATTERNS = [
    r"AWS_SECRET_ACCESS_KEY\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]",
    r"api[_-]?key\s*=\s*['\"][a-zA-Z0-9_-]{20,}['\"]",
    r"password\s*=\s*['\"].{8,}['\"]",
    r"token\s*=\s*['\"][a-zA-Z0-9_-]{20,}['\"]",
]

def audit_artifact(artifact_path: Path) -> dict:
    """Audit an artifact file. Returns {"result": "pass"|"fail", "warnings": [...], "errors": [...]}."""
    result = {"result": "pass", "warnings": [], "errors": []}
    
    if not artifact_path.exists():
        result["result"] = "fail"
        result["errors"].append(f"Artifact not found: {artifact_path}")
        return result
    
    try:
        text = artifact_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        result["result"] = "fail"
        result["errors"].append(f"Could not read artifact: {e}")
        return result

    # Strip markdown code blocks if present
    code_block_match = re.search(r"```(?:python|py)?\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        text = code_block_match.group(1).strip()
    elif text.startswith("```"):
        # Fallback for ill-formed blocks
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        text = "\n".join(lines)
        if "```" in text:
            text = text.split("```")[0]
        text = text.strip()
    
    # Secret scan
    for pattern in SECRET_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            result["result"] = "fail"
            result["errors"].append(f"Secret pattern detected: {pattern}")
    
    # Syntax check (basic)
    if artifact_path.suffix == ".py":
        try:
            compile(text, str(artifact_path), "exec")
        except SyntaxError as e:
            result["result"] = "fail"
            result["errors"].append(f"Syntax error: {e}")
    
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/audit.py <artifact_path>", file=sys.stderr)
        sys.exit(1)
    
    artifact_path = Path(sys.argv[1])
    result = audit_artifact(artifact_path)
    print(result["result"].upper())
    if result["errors"]:
        for err in result["errors"]:
            print(f"  ERROR: {err}", file=sys.stderr)
    if result["warnings"]:
        for warn in result["warnings"]:
            print(f"  WARN: {warn}")
    
    sys.exit(0 if result["result"] == "pass" else 1)
