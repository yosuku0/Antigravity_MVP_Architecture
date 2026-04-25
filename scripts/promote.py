#!/usr/bin/env python3
"""
promote.py — Stage artifact + promote to domain wiki

Usage:
    # Promote to default wiki/ (backward compatible)
    python scripts/promote.py <artifact_path>

    # Promote to specific domain wiki
    python scripts/promote.py <artifact_path> --domain game

    # Force promote (bypass Gate 3 — for recovery only)
    python scripts/promote.py <artifact_path> --domain market --force

Flow:
  1. Validate artifact exists
  2. If --domain: route to domains/{domain}/wiki/ instead of work/wiki/
  3. Check Gate 3 (CLI approval) unless --force
  4. Atomic copy to destination
  5. Update daemon state
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Allow importing from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domains.knowledge_os import KnowledgeOS, DomainError
from utils.atomic_io import atomic_write
from scripts.audit import audit_file


def compute_hash(path: Path) -> str:
    """SHA-256 of file contents for integrity verification."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def gate_3_approve(artifact_name: str, domain: str | None) -> bool:
    """HITL Gate 3 — CLI approval for wiki promotion."""
    dest = f"domains/{domain}/wiki/" if domain else "work/wiki/"
    print(f"\n{'='*60}")
    print(f"  GATE 3: Wiki Promotion Approval")
    print(f"{'='*60}")
    print(f"  Artifact : {artifact_name}")
    print(f"  Destination: {dest}")
    print(f"{'='*60}")
    choice = input("  Approve promotion? [y/N]: ").strip().lower()
    return choice == "y"


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote artifact to wiki")
    parser.add_argument("artifact", help="Path to artifact file")
    parser.add_argument(
        "--domain",
        choices=["game", "market", "personal"],
        default=None,
        help="Target domain wiki (default: work/wiki/)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Bypass Gate 3 (recovery only)"
    )
    parser.add_argument(
        "--force-reason",
        default=None,
        help="Required when --force is used. Explain why promotion bypass is necessary.",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help="Wiki topic slug (default: artifact filename without extension)",
    )
    parser.add_argument(
        "--squad",
        default=None,
        help="Squad name for permission checking",
    )
    args = parser.parse_args()

    if args.force and not args.force_reason:
        print("[ERROR] --force requires --force-reason")
        return 6

    artifact_path = Path(args.artifact)
    if not artifact_path.exists():
        print(f"[ERROR] Artifact not found: {artifact_path}")
        return 1

    # Determine topic
    topic = args.topic or artifact_path.stem
    # Ensure valid slug
    topic = topic.replace(" ", "_").replace("-", "_")[:60]

    # Content
    try:
        content = artifact_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"[ERROR] Artifact is not a text file: {artifact_path}")
        return 1

    # Pre-promotion audit (mandatory)
    audit_result = audit_file(artifact_path)
    if not audit_result.get("passed", False):
        if not args.force:
            print("[ERROR] Artifact audit failed. Promotion blocked.")
            print(json.dumps(audit_result, indent=2, ensure_ascii=False))
            return 5
        # --force used: allow bypass but log the failure
        print("[WARN] Artifact audit failed but --force is set. Proceeding with promotion.")
        print(json.dumps(audit_result, indent=2, ensure_ascii=False))

    # Gate 3
    if not args.force:
        if not gate_3_approve(artifact_path.name, args.domain):
            print("[Gate 3] REJECTED — promotion cancelled")
            return 2

    # Promote via KnowledgeOS (domain-aware) or fallback to filesystem
    try:
        if args.domain:
            kos = KnowledgeOS()
            wiki_path = kos.save(
                domain=args.domain,
                topic=topic,
                content=content,
                squad=args.squad,
                frontmatter={
                    "source_artifact": str(artifact_path),
                    "artifact_hash": compute_hash(artifact_path),
                    "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
            print(f"[OK] Promoted to domain wiki: {wiki_path}")
        else:
            # Backward-compatible: promote to work/wiki/
            dest_dir = Path("work/wiki")
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{topic}.md"

            # Add minimal frontmatter
            fm = {
                "topic": topic,
                "source_artifact": str(artifact_path),
                "artifact_hash": compute_hash(artifact_path),
                "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            import yaml
            fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True)
            doc = f"---\n{fm_yaml}---\n\n{content}\n"
            atomic_write(dest_path, doc)
            print(f"[OK] Promoted to work/wiki: {dest_path}")

    except DomainError as e:
        print(f"[ERROR] Domain validation failed: {e}")
        return 3
    except Exception as e:
        print(f"[ERROR] Promotion failed: {e}")
        return 4

    # Update daemon state log
    state_entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "op": "promote",
        "artifact": str(artifact_path),
        "topic": topic,
        "domain": args.domain,
        "hash": compute_hash(artifact_path),
    }
    from utils.atomic_io import atomic_append
    atomic_append(Path("work/daemon.jsonl"), json.dumps(state_entry))

    return 0


if __name__ == "__main__":
    sys.exit(main())
