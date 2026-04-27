"""
test_hitl_gated_promotion.py — SUPERSEDED by test_promotion_state_machine.py

This test assumed the old P0 design where Graph directly promoted to wiki
(approved_gate_1 -> audit_passed -> approved_gate_3 -> promoted via graph).

P0 fix: Graph stops at audit_passed. Promotion is handled exclusively by
scripts/promote.py via daemon dispatcher.

Full coverage is now in: tests/test_promotion_state_machine.py
"""
import pytest


@pytest.mark.xfail(
    reason=(
        "Superseded by P0 fix: Graph no longer promotes to wiki directly. "
        "Graph stops at audit_passed. Promotion handled by scripts/promote.py. "
        "See tests/test_promotion_state_machine.py for current regression coverage."
    ),
    strict=False,
)
def test_hitl_gated_promotion_flow(tmp_path, monkeypatch):
    """LEGACY: Full cycle via Graph promotion — no longer valid post P0 fix."""
    pytest.skip("Superseded by test_promotion_state_machine.py — see module docstring.")
