#!/usr/bin/env python3
"""
hermes_reflect.py — Wiki → Hermes memory reflection

Reads promoted wiki documents, indexes them into agentmemory vector store
for semantic retrieval by future squads.

Phase B enhancement: domain-aware indexing — each domain gets its own
ChromaDB collection for isolation.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domains.knowledge_os import KnowledgeOS, VALID_DOMAINS

# Try to import agentmemory
try:
    import agentmemory
    AGENTMEMORY_AVAILABLE = True
except ImportError:
    AGENTMEMORY_AVAILABLE = False


def extract_body(content: str) -> str:
    """Strip YAML frontmatter from wiki document."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content


def index_domain_wiki(domain: str, kos: KnowledgeOS) -> int:
    """Index all wiki documents for a domain into vector store."""
    if not AGENTMEMORY_AVAILABLE:
        print(f"[WARN] agentmemory not installed — skipping vector indexing for {domain}")
        return 0

    wiki_dir = kos.root / domain / "wiki"
    if not wiki_dir.exists():
        return 0

    collection_name = f"domain_{domain}"
    count = 0

    for path in wiki_dir.glob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
            body = extract_body(content)
            topic = path.stem

            agentmemory.store_memory(
                collection_name=collection_name,
                document=body,
                metadata={"topic": topic, "domain": domain, "source": str(path)},
            )
            count += 1
        except Exception as e:
            print(f"  [WARN] Failed to index {path}: {e}")

    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Wiki → Hermes reflection")
    parser.add_argument(
        "--domain",
        choices=list(VALID_DOMAINS),
        default=None,
        help="Index specific domain only",
    )
    parser.add_argument(
        "--all", action="store_true", help="Index all domains"
    )
    args = parser.parse_args()

    kos = KnowledgeOS()
    domains = [args.domain] if args.domain else list(VALID_DOMAINS) if args.all else []

    if not domains:
        print("Usage: --domain <name> | --all")
        return 1

    total = 0
    for domain in domains:
        print(f"Indexing domain:{domain} ...")
        count = index_domain_wiki(domain, kos)
        print(f"  Indexed {count} documents")
        total += count

    print(f"\nTotal indexed: {total} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
