import pytest
from pathlib import Path
import time
from apps.runtime.graph import run_job
from utils.atomic_io import read_frontmatter, write_frontmatter

def test_hitl_gated_promotion_flow(tmp_path, monkeypatch):
    """Test full cycle: JOB -> audit_passed -> manual approval -> promoted."""
    # Setup workspace
    work_dir = tmp_path / "work"
    jobs_dir = work_dir / "jobs"
    staging_dir = work_dir / "artifacts" / "staging"
    wiki_dir = tmp_path / "wiki" / "game"
    
    jobs_dir.mkdir(parents=True)
    staging_dir.mkdir(parents=True)
    (tmp_path / "domains" / "game" / "wiki").mkdir(parents=True)
    (tmp_path / "domains" / "game").mkdir(parents=True, exist_ok=True)
    (tmp_path / "domains" / "game" / ".domain").write_text("allowed_squads: [coding_squad]", encoding="utf-8")
    
    monkeypatch.chdir(tmp_path)
    
    job_id = "HITL-TEST-001"
    job_path = jobs_dir / f"{job_id}.md"
    job_path.write_text("---\ndomain: game\nstatus: approved_gate_1\n---\nWrite a simple function.", encoding="utf-8")
    
    # 1. First run: should stop at audit_passed
    def mock_run_executor(state):
        artifact_path = Path("work/artifacts/staging") / f"{state['job_id']}.md"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("Artifact Content", encoding="utf-8")
        return {**state, "status": "reviewing", "artifact_path": artifact_path}
    
    def mock_brain_review(state):
        return {**state, "status": "auditing"}
    
    monkeypatch.setattr("apps.runtime.graph.run_executor", mock_run_executor)
    monkeypatch.setattr("apps.runtime.graph.brain_review", mock_brain_review)
    
    result = run_job(str(job_path), job_id)
    assert result["status"] == "audit_passed", f"Status was {result.get('status')}, error: {result.get('error')}"
    
    # Verify JOB file was updated with audit_passed
    fm, _ = read_frontmatter(job_path)
    assert fm["status"] == "audit_passed"
    
    # 2. Manual Approval (simulate approve.py)
    fm["status"] = "approved_gate_3"
    fm["approved_gate_3_by"] = "test_user"
    write_frontmatter(job_path, fm, "Write a simple function.")
    
    # Reset KnowledgeOS singleton for test isolation
    from domains.knowledge_os import KnowledgeOS
    KnowledgeOS._instance = None
    kos = KnowledgeOS(root=tmp_path / "domains")
    
    # 3. Second run: should resume and finish at promoted
    result2 = run_job(str(job_path), job_id)
    assert result2["status"] == "promoted", f"Error: {result2.get('error')}"
    
    # Verify Wiki was updated
    # Path: domains/{domain}/wiki/{topic}.md
    wiki_file = tmp_path / "domains" / "game" / "wiki" / f"job_{job_id}.md"
    assert wiki_file.exists(), f"Wiki file not found at {wiki_file}"
    assert "Artifact Content" in wiki_file.read_text(encoding="utf-8")
    
    # Verify JOB file was NOT updated to promoted by the graph (graph status is promoted, but graph doesn't write back at the end of promote node yet)
    # Actually, promote_to_wiki node returns {status: promoted}. 
    # The run_job caller might need to handle the final write-back if we want the JOB file to show 'promoted'.
    # Current requirement: daemon saves result.get("status").
