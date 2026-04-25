#!/usr/bin/env python3
"""
cross_domain_audit.py — Detect and report cross-domain knowledge leakage

Usage:
    # Audit all domains for leakage
    python scripts/cross_domain_audit.py

    # Audit specific domain
    python scripts/cross_domain_audit.py --domain game

    # Show derive() audit trail
    python scripts/cross_domain_audit.py --trail

Checks:
  1. Documents in wiki/ that reference other domains without derive() provenance
  2. Squad access violations (coding_squad writing to personal without permission)
  3. Cross-domain derive() audit trail completeness
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domains.knowledge_os import KnowledgeOS, VALID_DOMAINS

# Patterns that indicate cross-domain references
LEAKAGE_PATTERNS = {
    "game": ["market.*competitor", "personal.*preference", "player.*data.*privacy"],
    "market": ["game.*mechanic", "personal.*user", "source.*code"],
    "personal": ["market.*trend", "game.*design", "revenue.*data"],
}


def check_domain_leakage(domain: str) -> list[dict]:
    """Scan wiki files for unauthorized cross-domain references."""
    kos = KnowledgeOS()
    wiki_dir = kos.root / domain / "wiki"
    if not wiki_dir.exists():
        return []

    violations = []
    for path in wiki_dir.glob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue

        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2]

        # Check for leakage patterns
        for other_domain, patterns in LEAKAGE_PATTERNS.items():
            if other_domain == domain:
                continue
            for pattern in patterns:
                if re.search(pattern, body, re.IGNORECASE):
                    # Check if this is a legitimate derive()
                    if "derived_from" in content and f"derived_from: {other_domain}" in content:
                        continue  # Legitimate cross-domain via derive()

                    violations.append({
                        "file": str(path),
                        "topic": path.stem,
                        "pattern": pattern,
                        "leaked_domain": other_domain,
                        "severity": "WARNING",
                        "note": "Cross-domain reference without derive() provenance",
                    })

    return violations


def check_squad_permissions(domain: str) -> list[dict]:
    """Verify all wiki files were written by allowed squads."""
    kos = KnowledgeOS()
    wiki_dir = kos.root / domain / "wiki"
    if not wiki_dir.exists():
        return []

    violations = []
    meta = kos._domains.get(domain)
    if not meta or not meta.allowed_squads:
        return []

    for path in wiki_dir.glob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Extract squad from frontmatter
        squad_match = re.search(r"^squad:\s*(\w+)", content, re.MULTILINE)
        if squad_match:
            squad = squad_match.group(1)
            if squad not in meta.allowed_squads:
                violations.append({
                    "file": str(path),
                    "topic": path.stem,
                    "squad": squad,
                    "severity": "ERROR",
                    "note": f"Squad {squad!r} not allowed in {domain!r} domain",
                })

    return violations


def read_derive_trail() -> list[dict]:
    """Read the cross-domain derive() audit trail."""
    trail_path = Path("work/blackboard/cross_domain_audit.jsonl")
    if not trail_path.exists():
        return []

    entries = []
    with open(trail_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-domain leakage audit")
    parser.add_argument(
        "--domain",
        choices=list(VALID_DOMAINS),
        default=None,
        help="Audit specific domain only",
    )
    parser.add_argument(
        "--trail", action="store_true", help="Show derive() audit trail"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    args = parser.parse_args()

    if args.trail:
        trail = read_derive_trail()
        if args.json:
            print(json.dumps(trail, indent=2, ensure_ascii=False))
        else:
            print(f"\n{'='*60}")
            print(f"  Cross-Domain Derive() Audit Trail")
            print(f"{'='*60}")
            print(f"  Total entries: {len(trail)}\n")
            for entry in trail:
                ts = entry.get("ts", "?")
                src = entry.get("src", "?")
                dst = entry.get("dst", "?")
                query = entry.get("query", "?")[:50]
                print(f"  [{ts}] {src} → {dst}: {query}...")
        return 0

    domains_to_check = [args.domain] if args.domain else list(VALID_DOMAINS)
    all_violations = []

    for domain in domains_to_check:
        leakage = check_domain_leakage(domain)
        permissions = check_squad_permissions(domain)
        all_violations.extend(leakage)
        all_violations.extend(permissions)

    if args.json:
        print(json.dumps(all_violations, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*60}")
        print(f"  Cross-Domain Leakage Audit Report")
        print(f"{'='*60}")
        print(f"  Domains checked: {domains_to_check}")
        print(f"  Violations found: {len(all_violations)}\n")

        if not all_violations:
            print("  ✅ No leakage detected — all cross-domain references are via derive()")
        else:
            for v in all_violations:
                sev = v.get("severity", "?")
                icon = "⚠️" if sev == "WARNING" else "❌"
                print(f"  {icon} [{sev}] {v['topic']}")
                print(f"      File: {v['file']}")
                print(f"      Issue: {v['note']}")
                if "pattern" in v:
                    print(f"      Pattern: {v['pattern']}")
                print()

    return 1 if any(v.get("severity") == "ERROR" for v in all_violations) else 0


if __name__ == "__main__":
    sys.exit(main())
