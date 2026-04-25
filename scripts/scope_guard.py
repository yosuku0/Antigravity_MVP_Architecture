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

def guard(path: Path) -> list[str]:
    violations = []
    for pyfile in path.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN:
            if forbidden in text:
                violations.append(f"{pyfile}: found '{forbidden}'")
    return violations

if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[1]
    v = guard(repo / "apps") + guard(repo / "scripts")
    if v:
        print("SCOPE VIOLATIONS FOUND:")
        for line in v:
            print(f"  {line}")
        sys.exit(1)
    print("Scope guard passed.")
    sys.exit(0)
