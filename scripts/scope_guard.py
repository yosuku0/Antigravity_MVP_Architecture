#!/usr/bin/env python3
"""
scope_guard.py — Forbidden import detection

Prevents unauthorized dependencies from entering the codebase.
Special-case: slack_bolt allowed only in apps/ingress/
"""

import argparse
import re
import sys
from pathlib import Path

# Module → reason
FORBIDDEN = {
    "requests": "Use urllib from stdlib",
    "httpx": "Use urllib from stdlib",
    "subprocess": "Use e2b sandbox for execution",
}

# Module → allowed paths
ALLOWED_PATHS = {
    "slack_bolt": ["apps/ingress/"],
    "slack_sdk": ["apps/ingress/"],
}

IMPORT_RE = re.compile(r"^(?:import\s+(\S+)|from\s+(\S+)\s+import)", re.MULTILINE)


def scan_file(path: Path, root: Path) -> list[dict]:
    """Scan a single file for forbidden imports."""
    findings = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings

    rel = str(path.relative_to(root))

    for match in IMPORT_RE.finditer(content):
        module = match.group(1) or match.group(2)
        base = module.split(".")[0]

        # Check forbidden
        if base in FORBIDDEN:
            findings.append({
                "file": rel,
                "line": content[:match.start()].count("\n") + 1,
                "module": base,
                "reason": FORBIDDEN[base],
                "severity": "ERROR",
            })

        # Check restricted paths
        if base in ALLOWED_PATHS:
            if not any(a in rel for a in ALLOWED_PATHS[base]):
                findings.append({
                    "file": rel,
                    "line": content[:match.start()].count("\n") + 1,
                    "module": base,
                    "reason": f"Allowed only in: {ALLOWED_PATHS[base]}",
                    "severity": "ERROR",
                })

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scope guard")
    parser.add_argument("root", nargs="?", default=".", help="Project root")
    args = parser.parse_args()

    root = Path(args.root)
    all_findings = []

    for path in root.rglob("*.py"):
        if "vendor/" in str(path):
            continue  # Skip vendored code
        all_findings.extend(scan_file(path, root))

    if all_findings:
        print(f"\n❌ Scope violations found: {len(all_findings)}")
        for f in all_findings:
            print(f"  {f['file']}:{f['line']} — {f['module']} ({f['reason']})")
        return 1

    print("✅ Scope guard passed — no forbidden imports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
