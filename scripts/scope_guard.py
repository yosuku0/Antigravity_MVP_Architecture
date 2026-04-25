#!/usr/bin/env python3
"""Scope Guard — prevents deferred capabilities from entering MVP."""
import sys
from pathlib import Path

FORBIDDEN = [
    "slack_bolt",      # Slack ingress deferred
    "slack_sdk",       # Slack ingress deferred
    "qdrant_client",   # Qdrant RAG deferred — wait, this is in requirements.txt
    # NOTE: qdrant-client is installed but runtime code must not use it in MVP
]

def guard(path: Path, forbidden_list: list[str], exclude_path: str = None) -> list[str]:
    violations = []
    for pyfile in path.rglob("*.py"):
        if exclude_path and exclude_path in str(pyfile.as_posix()):
            continue
        text = pyfile.read_text(encoding="utf-8")
        for forbidden in forbidden_list:
            if forbidden in text:
                violations.append(f"{pyfile}: found '{forbidden}'")
    return violations

if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[1]
    
    # Slack is now allowed in apps/ingress, but still forbidden everywhere else
    slack_forbidden = ["slack_bolt", "slack_sdk"]
    other_forbidden = ["qdrant_client"]
    
    v = []
    # Check apps/ingress separately (allow slack, forbid others)
    v += guard(repo / "apps" / "ingress", other_forbidden)
    
    # Check everything else (forbid all)
    all_forbidden = slack_forbidden + other_forbidden
    
    # Check apps/daemon, apps/runtime, apps/llm_router, etc.
    for subdir in ["daemon", "runtime", "llm_router", "crew"]:
        v += guard(repo / "apps" / subdir, all_forbidden)
        
    # Check scripts
    v += guard(repo / "scripts", all_forbidden)
    
    if v:
        print("SCOPE VIOLATIONS FOUND:")
        for line in v:
            print(f"  {line}")
        sys.exit(1)
    print("Scope guard passed.")
    sys.exit(0)
