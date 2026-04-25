#!/usr/bin/env python3
"""
audit.py — Artifact security and quality audit

Checks:
  1. Secret scan (API keys, tokens, passwords)
  2. Syntax validation (Python, JSON, YAML)
  3. Scope guard (forbidden imports)
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Secret patterns
SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI-style API key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth token"),
    (r"xox[baprs]-[0-9a-zA-Z\-]+", "Slack token"),
    (r"\b[0-9a-f]{64}\b", "Hex secret (64 chars)"),
    # Anthropic API key
    (r"sk-ant-[a-zA-Z0-9\-_]{20,}", "Anthropic"),
    # NVIDIA NIM API key
    (r"nvapi-[a-zA-Z0-9\-_]{20,}", "NVIDIA NIM"),
    # Google / Gemini API key
    (r"AIza[0-9A-Za-z\-_]{35}", "Google/Gemini"),
    # Moonshot / Kimi API key
    (r"moonshot-[a-zA-Z0-9\-_]{20,}", "Moonshot"),
]

# Scope-guard forbidden imports (with exceptions)
FORBIDDEN_IMPORTS = {
    "requests": "Use urllib from stdlib instead",
    "subprocess": "Sandboxed execution only via e2b",
}

ALLOWED_PATHS = {
    "slack_bolt": ["apps/ingress/"],  # slack_bolt allowed only in ingress
}


def scan_secrets(content: str) -> list[dict]:
    """Scan content for potential secrets."""
    findings = []
    for pattern, description in SECRET_PATTERNS:
        for match in re.finditer(pattern, content):
            findings.append({
                "type": "secret",
                "description": description,
                "match": match.group()[:20] + "...",
                "position": match.start(),
            })
    return findings


def check_syntax(path: Path, content: str) -> list[dict]:
    """Validate file syntax."""
    findings = []
    suffix = path.suffix.lower()

    if suffix == ".py":
        import py_compile
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as e:
            findings.append({"type": "syntax", "description": str(e)})

    elif suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            findings.append({"type": "syntax", "description": str(e)})

    elif suffix in (".yaml", ".yml"):
        try:
            import yaml
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            findings.append({"type": "syntax", "description": str(e)})

    return findings


def check_scope(content: str, relative_path: str) -> list[dict]:
    """Check for forbidden imports."""
    findings = []
    for module, reason in FORBIDDEN_IMPORTS.items():
        pattern = rf"^(import\s+{module}|from\s+{module}\s+import)"
        if re.search(pattern, content, re.MULTILINE):
            findings.append({
                "type": "scope",
                "description": f"Forbidden import: {module}",
                "reason": reason,
            })

    # Special-case allowed paths
    for module, allowed in ALLOWED_PATHS.items():
        pattern = rf"^(import\s+{module}|from\s+{module}\s+import)"
        if re.search(pattern, content, re.MULTILINE):
            if not any(a in relative_path for a in allowed):
                findings.append({
                    "type": "scope",
                    "description": f"Forbidden import: {module} in {relative_path}",
                    "reason": f"Allowed only in: {allowed}",
                })

    return findings


def audit_file(path: Path, relative_to: Path | None = None) -> dict:
    """Run full audit on a single file."""
    result = {
        "file": str(path),
        "findings": [],
        "passed": True,
    }

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {**result, "note": "Binary file skipped"}

    rel_path = str(path.relative_to(relative_to)) if relative_to else str(path)

    result["findings"].extend(scan_secrets(content))
    result["findings"].extend(check_syntax(path, content))
    result["findings"].extend(check_scope(content, rel_path))

    result["passed"] = len(result["findings"]) == 0
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Artifact audit")
    parser.add_argument("path", help="File or directory to audit")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    target = Path(args.path)
    results = []

    if target.is_file():
        results.append(audit_file(target))
    elif target.is_dir():
        for path in target.rglob("*"):
            if path.is_file() and path.suffix in (".py", ".json", ".yaml", ".yml", ".md", ".js", ".ts"):
                results.append(audit_file(path, target))
    else:
        print(f"[ERROR] Path not found: {target}")
        return 1

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    if args.json:
        print(json.dumps({
            "summary": {"passed": passed, "total": total},
            "results": results,
        }, indent=2, ensure_ascii=False))
    else:
        print(f"\nAudit: {passed}/{total} files passed")
        for r in results:
            if not r["passed"]:
                print(f"\n  ❌ {r['file']}")
                for f in r["findings"]:
                    print(f"     [{f['type'].upper()}] {f['description']}")

    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
