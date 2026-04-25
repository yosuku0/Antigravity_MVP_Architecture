"""Test Brain↔Developer feedback loop (Phase C L2)."""
from pathlib import Path
import tempfile
import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.runtime.graph import State, brain_review, execute_squads


class TestBrainLoop:
    """Test the brain review feedback loop."""
    
    def test_brain_review_approved(self):
        """Test brain_review when artifact passes."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# Test Artifact\n\nThis is a sufficiently long artifact with no issues and it passes all checks. It needs to be more than 100 characters to pass the placeholder check.")
            tmp = Path(f.name)
        
        state: State = {
            "job_id": "TEST-LOOP-001",
            "job_path": tmp,
            "status": "executing",
            "routing_context": "",
            "squads": ["coding_squad"],
            "target_domain": "game",
            "audit_result": "",
            "error": None,
            "review_feedback": None,
            "review_count": 0,
            "artifact_path": tmp,
        }
        
        result = brain_review(state)
        assert result["status"] == "auditing"
        assert result["review_count"] == 1
    
    def test_brain_review_rejected(self):
        """Test brain_review when artifact fails."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# Short")
            tmp = Path(f.name)
        
        state: State = {
            "job_id": "TEST-LOOP-002",
            "job_path": tmp,
            "status": "executing",
            "routing_context": "",
            "squads": ["coding_squad"],
            "target_domain": "game",
            "audit_result": "",
            "error": None,
            "review_feedback": None,
            "review_count": 0,
            "artifact_path": tmp,
        }
        
        result = brain_review(state)
        assert result["status"] == "reviewing"
        assert result["review_feedback"] is not None
        assert result["review_count"] == 1
    
    def test_review_count_limit(self):
        """Test that review loop stops after 3 iterations."""
        state: State = {
            "job_id": "TEST-LOOP-003",
            "job_path": Path("nonexistent.md"),
            "status": "executing",
            "routing_context": "",
            "squads": ["coding_squad"],
            "target_domain": "game",
            "audit_result": "",
            "error": None,
            "review_feedback": "some feedback",
            "review_count": 3,  # Already at limit
            "artifact_path": None,
        }
        
        result = brain_review(state)
        # count becomes 4
        assert result["review_count"] == 4
    
    def test_feedback_injection(self):
        """Test that review_feedback is injected into objective."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# Original Task\n\nImplement feature X.")
            tmp = Path(f.name)
        
        state: State = {
            "job_id": "TEST-LOOP-004",
            "job_path": tmp,
            "status": "executing",
            "routing_context": "",
            "squads": [],
            "target_domain": "game",
            "audit_result": "",
            "error": None,
            "review_feedback": "Fix the typo in section 2",
            "review_count": 1,
            "artifact_path": None,
        }
        
        # execute_squads should inject feedback into objective
        result = execute_squads(state)
        assert result["review_feedback"] is None  # Cleared after use
        assert result["artifact_path"] is not None
        assert result["status"] == "reviewing"
