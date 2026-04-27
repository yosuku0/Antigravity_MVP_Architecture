"""
test_hitl_gated_promotion.py — SUPERSEDED by tests/test_promotion_state_machine.py

This test assumed the old design where the Graph directly promoted to the wiki.
Following the P0 fix, the Graph stops at audit_passed, and promotion is handled 
exclusively by scripts/promote.py via the daemon dispatcher.

Regression coverage for the current state machine is consolidated in:
tests/test_promotion_state_machine.py
"""
import pytest

# Mark the entire module as skipped as it tests a deprecated/superseded design.
pytestmark = pytest.mark.skip(reason="Superseded by tests/test_promotion_state_machine.py")
