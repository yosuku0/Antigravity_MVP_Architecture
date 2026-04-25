"""
L1 Knowledge OS — Karpathy 4-Operation Model

Implements domain-aware knowledge management with strict isolation:
  save(domain, topic, content)  → Write to single-domain wiki
  load(domain, topic)           → Read from single-domain wiki
  search(domain, query)         → Vector search within single domain
  derive(src, dst, query)       → Cross-domain synthesis (AUDITED)

Cross-domain leakage prevention:
  - Each domain has its own ChromaDB collection (B-005)
  - derive() is the ONLY cross-domain operation
  - All derive() calls are logged to work/blackboard/cross_domain_audit.jsonl
"""

from __future__ import annotations

import json
import os
import re
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Try to import agentmemory for vector search (B-005 integration)
try:
    import agentmemory
    AGENTMEMORY_AVAILABLE = True
except ImportError:
    AGENTMEMORY_AVAILABLE = False

from utils.atomic_io import atomic_write, atomic_append


class DomainError(Exception):
    """Raised on invalid domain operations."""
    pass


class CrossDomainLeakError(DomainError):
    """Raised when an unauthorized cross-domain access is detected."""
    pass


class SquadPermissionError(DomainError):
    """Raised when a squad attempts to access a disallowed domain."""
    pass


@dataclass
class DomainMeta:
    """Metadata parsed from a .domain file."""
    name: str
    description: str
    allowed_squads: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> "DomainMeta":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            name=data.get("name", path.parent.name),
            description=data.get("description", ""),
            allowed_squads=data.get("allowed_squads", []),
        )


# Module-level lock for singleton thread-safety
_lock = threading.Lock()


class KnowledgeOS:
    """Domain-aware knowledge operating system.

    Usage:
        kos = KnowledgeOS(Path("domains"))
        kos.save("game", "combat_system", "## Combat\n...", squad="coding_squad")
        doc = kos.load("game", "combat_system")
        results = kos.search("game", "combat mechanics")
        synthesis = kos.derive("game", "market", "combat trends")
    """

    VALID_DOMAINS = {"game", "market", "personal"}
    _instance: KnowledgeOS | None = None

    def __new__(cls, *args, **kwargs):
        """Singleton — one KnowledgeOS per process."""
        with _lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, root: Path | None = None):
        if self._initialized:
            return
        if root is None:
            root = Path(__file__).resolve().parent
        self.root = Path(root)
        self._domains: dict[str, DomainMeta] = {}
        self._audit_path = Path("work/blackboard/cross_domain_audit.jsonl")
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_collections()
        self._initialized = True

    def _init_collections(self) -> None:
        """Load domain metadata and initialize vector collections."""
        for name in self.VALID_DOMAINS:
            domain_file = self.root / name / ".domain"
            if domain_file.exists():
                self._domains[name] = DomainMeta.from_file(domain_file)
            else:
                self._domains[name] = DomainMeta(
                    name=name,
                    description=f"{name} knowledge domain",
                    allowed_squads=["coding_squad", "research_squad", "review_squad"],
                )

    # ── Helpers ──────────────────────────────────────────────────────────

    def _wiki_path(self, domain: str, topic: str) -> Path:
        """Canonical path: domains/{domain}/wiki/{topic}.md"""
        if not re.match(r"^[\w\-]+$", topic):
            raise DomainError(f"Invalid topic name: {topic!r}")
        return self.root / domain / "wiki" / f"{topic}.md"

    def _raw_path(self, domain: str, filename: str) -> Path:
        """Canonical raw path: domains/{domain}/raw/{filename}"""
        return self.root / domain / "raw" / filename

    def _validate_domain(self, domain: str) -> None:
        if domain not in self.VALID_DOMAINS:
            raise DomainError(
                f"Invalid domain {domain!r}. Valid: {self.VALID_DOMAINS}"
            )

    def _validate_squad(self, domain: str, squad: str | None) -> None:
        """Enforce squad permissions from .domain files."""
        if squad is None:
            return  # Internal/system calls bypass squad check
        meta = self._domains.get(domain)
        if meta and meta.allowed_squads and squad not in meta.allowed_squads:
            raise SquadPermissionError(
                f"Squad {squad!r} is not allowed in domain {domain!r}. "
                f"Allowed: {meta.allowed_squads}"
            )

    def _log_derive(self, src: str, dst: str, query: str, result: str) -> None:
        """Audit trail for all cross-domain derive() operations."""
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "op": "derive",
            "src": src,
            "dst": dst,
            "query": query,
            "result_hash": hash(result) & 0xFFFFFFFF,
        }
        atomic_append(self._audit_path, json.dumps(entry, ensure_ascii=False))

    # ── 1. SAVE ──────────────────────────────────────────────────────────

    def save(
        self,
        domain: str,
        topic: str,
        content: str,
        *,
        squad: str | None = None,
        frontmatter: dict[str, Any] | None = None,
    ) -> Path:
        """Write content to domain wiki/ with YAML frontmatter.

        Args:
            domain: One of game | market | personal
            topic: Wiki topic slug (alphanumeric + hyphens)
            content: Markdown content body
            squad: Calling squad name (for permission check)
            frontmatter: Additional YAML frontmatter fields

        Returns:
            Path to the written file

        Raises:
            DomainError: Invalid domain or topic
            SquadPermissionError: Squad not allowed in domain
        """
        self._validate_domain(domain)
        self._validate_squad(domain, squad)

        fm = {
            "domain": domain,
            "topic": topic,
            "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if squad:
            fm["squad"] = squad
        if frontmatter:
            fm.update(frontmatter)

        fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True)
        doc = f"---\n{fm_yaml}---\n\n{content}\n"

        path = self._wiki_path(domain, topic)
        atomic_write(path, doc)

        # Auto-index into vector store (B-005 integration)
        self._index_document(domain, topic, content)

        return path

    # ── 2. LOAD ──────────────────────────────────────────────────────────

    def load(self, domain: str, topic: str, *, squad: str | None = None) -> str:
        """Read document from domain wiki/.

        Returns:
            Full document content including YAML frontmatter

        Raises:
            DomainError: Invalid domain
            SquadPermissionError: Squad not allowed in domain
            FileNotFoundError: Topic does not exist
        """
        self._validate_domain(domain)
        self._validate_squad(domain, squad)

        path = self._wiki_path(domain, topic)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def load_body(self, domain: str, topic: str, *, squad: str | None = None) -> str:
        """Read only the markdown body (strip YAML frontmatter)."""
        content = self.load(domain, topic, squad=squad)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content

    # ── 3. SEARCH ────────────────────────────────────────────────────────

    def search(
        self, domain: str, query: str, *, n_results: int = 5, squad: str | None = None
    ) -> list[dict[str, Any]]:
        """Vector search within a single domain's knowledge collection.

        Uses agentmemory (ChromaDB) when available, falls back to
        filename grep for MVP without vector store.

        Returns:
            List of result dicts with keys: topic, content, distance
        """
        self._validate_domain(domain)
        self._validate_squad(domain, squad)

        if AGENTMEMORY_AVAILABLE:
            return self._vector_search(domain, query, n_results=n_results)

        # Fallback: grep over wiki filenames + basic content scan
        return self._fallback_search(domain, query, n_results=n_results)

    # ── 4. DERIVE ────────────────────────────────────────────────────────

    def derive(
        self,
        src: str,
        dst: str,
        query: str,
        *,
        squad: str | None = None,
    ) -> dict[str, Any]:
        """Cross-domain knowledge synthesis — the ONLY cross-domain operation.

        Searches the source domain, synthesizes insights, and saves the
        result to the destination domain. Leaves an audit trail.

        Args:
            src: Source domain to search
            dst: Destination domain to save synthesis
            query: Search/synthesis query
            squad: Calling squad (must be allowed in BOTH domains)

        Returns:
            Dict with keys: saved_path, sources (list), synthesis (str)

        Raises:
            CrossDomainLeakError: If squad lacks permission in either domain
        """
        self._validate_domain(src)
        self._validate_domain(dst)

        # Enforce: squad must be allowed in BOTH domains
        if squad:
            try:
                self._validate_squad(src, squad)
                self._validate_squad(dst, squad)
            except SquadPermissionError as e:
                raise CrossDomainLeakError(
                    f"derive() blocked: squad {squad!r} lacks cross-domain permission. {e}"
                ) from e

        # Prevent same-domain derive (that's just save)
        if src == dst:
            raise DomainError("derive() requires different src and dst domains")

        # Search source domain
        results = self.search(src, query, squad=squad)
        if not results:
            synthesis = f"## Cross-Domain Synthesis: {src} → {dst}\n\n"
            synthesis += f"**Query:** {query}\n\n"
            synthesis += "_No matching documents found in source domain._\n"
        else:
            synthesis = self._synthesize(src, dst, query, results)

        # Save to destination domain
        topic = f"derived_{src}_{self._slugify(query)}"
        path = self.save(
            dst,
            topic,
            synthesis,
            squad=squad,
            frontmatter={"derived_from": src, "derive_query": query},
        )

        # Audit trail
        self._log_derive(src, dst, query, synthesis)

        return {
            "saved_path": str(path),
            "sources": [r.get("topic", "?") for r in results],
            "synthesis": synthesis,
        }

    # ── Internal: Vector Search (B-005) ─────────────────────────────────

    def _index_document(self, domain: str, topic: str, content: str) -> None:
        """Auto-index document into domain-specific ChromaDB collection."""
        if not AGENTMEMORY_AVAILABLE:
            return
        try:
            collection_name = f"domain_{domain}"
            agentmemory.store_memory(
                collection_name=collection_name,
                document=content,
                metadata={"topic": topic, "domain": domain},
            )
        except Exception:
            # Silently fail — vector search is enhancement, not requirement
            pass

    def _vector_search(
        self, domain: str, query: str, *, n_results: int = 5
    ) -> list[dict[str, Any]]:
        """Search using agentmemory vector store."""
        collection_name = f"domain_{domain}"
        try:
            memories = agentmemory.search_memory(
                collection_name=collection_name,
                query=query,
                n_results=n_results,
            )
            return [
                {
                    "topic": m.get("metadata", {}).get("topic", "unknown"),
                    "content": m.get("document", ""),
                    "distance": m.get("distance", 0.0),
                }
                for m in memories
            ]
        except Exception:
            return []

    def _fallback_search(
        self, domain: str, query: str, *, n_results: int = 5
    ) -> list[dict[str, Any]]:
        """Greedy text search over wiki files — no vector store needed."""
        wiki_dir = self.root / domain / "wiki"
        if not wiki_dir.exists():
            return []

        terms = query.lower().split()
        scored: list[tuple[float, Path]] = []

        for path in wiki_dir.glob("*.md"):
            try:
                text = path.read_text(encoding="utf-8").lower()
                score = sum(1 for term in terms if term in text)
                if score > 0:
                    scored.append((score, path))
            except Exception:
                continue

        scored.sort(reverse=True)
        results = []
        for score, path in scored[:n_results]:
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                content = ""
            results.append(
                {
                    "topic": path.stem,
                    "content": content[:1000],  # Truncate for brevity
                    "distance": 1.0 / (score + 1),
                }
            )
        return results

    # ── Internal: Synthesis ──────────────────────────────────────────────

    def _synthesize(
        self, src: str, dst: str, query: str, results: list[dict[str, Any]]
    ) -> str:
        """Build a cross-domain synthesis document from search results."""
        lines = [
            f"## Cross-Domain Synthesis: {src} → {dst}",
            "",
            f"**Query:** {query}",
            f"**Sources:** {len(results)} documents from `{src}` domain",
            "",
            "### Source Excerpts",
            "",
        ]
        for i, r in enumerate(results, 1):
            lines.append(f"**{i}. {r.get('topic', '?')}**")
            excerpt = r.get("content", "")[:500].replace("\n", " ")
            lines.append(f"> {excerpt}...")
            lines.append("")

        lines.extend([
            "### Synthesis",
            "",
            "_Synthesize insights from the source domain excerpts above. "
            "Connect patterns to the destination domain context._",
            "",
        ])
        return "\n".join(lines)

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert query to filesystem-safe slug."""
        return re.sub(r"[^\w\-]+", "_", text.lower()).strip("_")[:60]
