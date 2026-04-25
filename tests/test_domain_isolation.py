"""
test_domain_isolation.py — Verify L1 Knowledge OS domain boundaries

Tests B-001 through B-005:
  - Domain directory structure
  - Karpathy 4-operation model (save/load/search/derive)
  - Squad permission enforcement
  - Cross-domain leakage prevention
  - Audit trail completeness
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Set up project root import
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from domains.knowledge_os import (
    KnowledgeOS,
    DomainError,
    CrossDomainLeakError,
    SquadPermissionError,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def temp_domains(tmp_path: Path):
    """Create an isolated domains/ tree for testing."""
    domains_root = tmp_path / "domains"
    for name in ("game", "market", "personal"):
        (domains_root / name / "raw").mkdir(parents=True)
        (domains_root / name / "wiki").mkdir(parents=True)
        # Create .domain files
        (domains_root / name / ".domain").write_text(
            f"name: {name}\n"
            f"description: Test {name} domain\n"
            f"allowed_squads:\n  - coding_squad\n  - research_squad\n  - review_squad\n",
            encoding="utf-8",
        )
    return domains_root


@pytest.fixture
def kos(temp_domains: Path):
    """Fresh KnowledgeOS instance pointed at temp domains."""
    # Reset singleton
    KnowledgeOS._instance = None
    os.chdir(temp_domains.parent)
    instance = KnowledgeOS(temp_domains)
    # Create blackboard dir
    (temp_domains.parent / "work" / "blackboard").mkdir(parents=True, exist_ok=True)
    instance._audit_path = temp_domains.parent / "work" / "blackboard" / "cross_domain_audit.jsonl"
    return instance


# ── B-001: Domain Structure ─────────────────────────────────────────

class TestB001DomainStructure:
    def test_domain_directories_exist(self, temp_domains: Path):
        for name in ("game", "market", "personal"):
            assert (temp_domains / name / "raw").exists()
            assert (temp_domains / name / "wiki").exists()
            assert (temp_domains / name / ".domain").exists()

    def test_domain_metadata_parsed(self, kos: KnowledgeOS):
        meta = kos._domains["game"]
        assert meta.name == "game"
        assert "coding_squad" in meta.allowed_squads


# ── B-002: Karpathy 4-Op Model ──────────────────────────────────────

class TestB002KarpathyFourOp:
    def test_save_creates_file(self, kos: KnowledgeOS, temp_domains: Path):
        path = kos.save("game", "combat_system", "## Combat\nDetails here", squad="coding_squad")
        assert path.exists()
        assert path.name == "combat_system.md"
        assert path.parent == temp_domains / "game" / "wiki"

    def test_save_includes_frontmatter(self, kos: KnowledgeOS):
        kos.save("game", "mechanics", "Content", squad="coding_squad")
        doc = kos.load("game", "mechanics")
        assert doc.startswith("---")
        assert "domain: game" in doc
        assert "topic: mechanics" in doc
        assert "squad: coding_squad" in doc

    def test_load_body_strips_frontmatter(self, kos: KnowledgeOS):
        kos.save("market", "trends", "## Trends\nData here", squad="research_squad")
        body = kos.load_body("market", "trends")
        assert not body.startswith("---")
        assert "## Trends" in body

    def test_save_invalid_domain_raises(self, kos: KnowledgeOS):
        with pytest.raises(DomainError):
            kos.save("invalid", "topic", "content")

    def test_save_invalid_topic_raises(self, kos: KnowledgeOS):
        with pytest.raises(DomainError):
            kos.save("game", "bad/topic", "content")

    def test_load_nonexistent_raises(self, kos: KnowledgeOS):
        with pytest.raises(FileNotFoundError):
            kos.load("game", "nonexistent")


# ── B-003: Squad Permissions ────────────────────────────────────────

class TestB003SquadPermissions:
    def test_allowed_squad_can_save(self, kos: KnowledgeOS):
        # All squads allowed in test fixtures
        kos.save("game", "test1", "content", squad="coding_squad")
        kos.save("game", "test2", "content", squad="research_squad")

    def test_disallowed_squad_raises(self, kos: KnowledgeOS, temp_domains: Path):
        # Restrict game domain to only coding_squad
        (temp_domains / "game" / ".domain").write_text(
            "name: game\nallowed_squads:\n  - coding_squad\n",
            encoding="utf-8",
        )
        # Refresh
        KnowledgeOS._instance = None
        kos2 = KnowledgeOS(temp_domains)
        kos2._audit_path = temp_domains.parent / "work" / "blackboard" / "cross_domain_audit.jsonl"

        with pytest.raises(SquadPermissionError):
            kos2.save("game", "test3", "content", squad="research_squad")


# ── B-004: Cross-Domain Leakage Prevention ──────────────────────────

class TestB004CrossDomainLeakage:
    def test_derive_same_domain_raises(self, kos: KnowledgeOS):
        with pytest.raises(DomainError):
            kos.derive("game", "game", "combat")

    def test_derive_creates_synthesis(self, kos: KnowledgeOS, temp_domains: Path):
        # Seed source domain
        kos.save("game", "combat", "## Combat\nTurn-based system", squad="coding_squad")
        result = kos.derive("game", "market", "combat analysis")
        assert result["saved_path"]
        assert "combat" in result["sources"]  # Topic name, not domain
        assert "Synthesis" in result["synthesis"]

    def test_derive_logs_audit_trail(self, kos: KnowledgeOS, temp_domains: Path):
        kos.save("game", "data", "Game analytics", squad="coding_squad")
        kos.derive("game", "market", "analytics trends")
        # Check audit log
        audit_path = temp_domains.parent / "work" / "blackboard" / "cross_domain_audit.jsonl"
        assert audit_path.exists()
        lines = audit_path.read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["op"] == "derive"
        assert entry["src"] == "game"
        assert entry["dst"] == "market"

    def test_derive_checks_squad_permissions(self, kos: KnowledgeOS, temp_domains: Path):
        # Restrict market domain
        (temp_domains / "market" / ".domain").write_text(
            "name: market\nallowed_squads:\n  - research_squad\n",
            encoding="utf-8",
        )
        KnowledgeOS._instance = None
        kos2 = KnowledgeOS(temp_domains)
        kos2._audit_path = temp_domains.parent / "work" / "blackboard" / "cross_domain_audit.jsonl"

        # coding_squad not allowed in market → derive should fail
        with pytest.raises(CrossDomainLeakError):
            kos2.derive("game", "market", "test", squad="coding_squad")


# ── B-005: Search ───────────────────────────────────────────────────

class TestB005Search:
    def test_fallback_search_finds_content(self, kos: KnowledgeOS):
        kos.save("game", "combat", "## Combat Mechanics\nTurn-based combat system", squad="coding_squad")
        kos.save("game", "story", "## Narrative\nBranching storyline", squad="coding_squad")
        results = kos.search("game", "combat mechanics")
        assert len(results) > 0
        topics = [r["topic"] for r in results]
        assert "combat" in topics

    def test_search_invalid_domain_raises(self, kos: KnowledgeOS):
        with pytest.raises(DomainError):
            kos.search("invalid", "query")


# ── Integration ───────────────────────────────────────────────────────

class TestIntegration:
    def test_full_workflow(self, kos: KnowledgeOS, temp_domains: Path):
        """E2E: save → search → derive → audit trail"""
        # 1. Save multiple docs to game domain
        kos.save("game", "combat", "## Combat\nTurn-based with elements", squad="coding_squad")
        kos.save("game", "progression", "## Progression\nXP and leveling", squad="coding_squad")

        # 2. Search within domain
        results = kos.search("game", "combat elements")
        assert any(r["topic"] == "combat" for r in results)

        # 3. Derive to market
        result = kos.derive("game", "market", "monetization potential")
        assert Path(result["saved_path"]).exists()

        # 4. Verify audit trail
        audit_path = temp_domains.parent / "work" / "blackboard" / "cross_domain_audit.jsonl"
        entries = [json.loads(line) for line in audit_path.read_text().strip().split("\n")]
        derive_entries = [e for e in entries if e["op"] == "derive"]
        assert len(derive_entries) >= 1
        assert derive_entries[0]["src"] == "game"
        assert derive_entries[0]["dst"] == "market"

        # 5. Verify isolation: market search finds derived doc by its content
        market_results = kos.search("market", "monetization")
        # The derived document should be findable
        assert any("derived_game" in r.get("topic", "") for r in market_results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
