import json
from typing import TypedDict, Optional
from pathlib import Path
from datetime import datetime, timezone
from langgraph.graph import StateGraph, END
import sys

# Ensure utils can be imported
sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.atomic_io import read_frontmatter

class State(TypedDict):
    job_id: str
    job_path: str
    status: str          # From frontmatter
    routing_context: str # "classify_local" for MVP
    artifact_path: str   # Path to generated artifact
    audit_result: Optional[str] # "pass", "fail", or None
    crew_result: Optional[str]

def load_job_node(state: State) -> State:
    """Read YAML frontmatter and validate Gate 1 approval."""
    job_path = Path(state["job_path"])
    if not job_path.exists():
        raise FileNotFoundError(f"Job file not found: {job_path}")
        
    frontmatter, _ = read_frontmatter(job_path)
    status = frontmatter.get("status")
    
    # Safety gate: If status not in approved set, raise error
    approved_statuses = {"approved_gate_1", "claimed", "routed"}
    if status not in approved_statuses:
        raise ValueError(f"Gate 1 not approved. JOB blocked. Current status: {status}")
        
    # Log to job_results.jsonl
    repo_root = Path(__file__).resolve().parents[2]
    log_dir = repo_root / "runtime" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "job_results.jsonl"
    
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "job_loaded",
        "job_id": job_path.stem,
        "status": status
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
        
    return {
        **state,
        "job_id": job_path.stem,
        "status": status
    }

def router_node(state: State) -> State:
    """Route the job to a context. Placeholder for MVP."""
    # TODO: Replace with real routing in Block C (C-006)
    return {
        **state,
        "routing_context": "classify_local"
    }

def crew_execute_node(state: State) -> State:
    """Placeholder for CrewAI execution. Real implementation in B-006."""
    # This will be replaced in B-006
    job_id = state.get("job_id", "unknown")
    repo_root = Path(__file__).resolve().parents[2]
    working_dir = repo_root / "memory" / "working" / job_id
    working_dir.mkdir(parents=True, exist_ok=True)
    
    artifact_path = working_dir / "artifact.py"
    artifact_path.write_text("# Hello World\nprint('hello')", encoding="utf-8")
    
    return {
        **state,
        "artifact_path": str(artifact_path),
        "crew_result": "Success (Placeholder)"
    }

def audit_node(state: State) -> State:
    """Minimal audit check. Real integration in B-007."""
    path_str = state.get("artifact_path", "")
    if path_str:
        path = Path(path_str)
        if path.exists():
            audit_result = "pass"
        else:
            audit_result = "fail"
    else:
        audit_result = "fail"
        
    return {
        **state,
        "audit_result": audit_result
    }

# Graph definition
workflow = StateGraph(State)

workflow.add_node("load_job", load_job_node)
workflow.add_node("router", router_node)
workflow.add_node("crew_execute", crew_execute_node)
workflow.add_node("audit", audit_node)

workflow.set_entry_point("load_job")
workflow.add_edge("load_job", "router")
workflow.add_edge("router", "crew_execute")
workflow.add_edge("crew_execute", "audit")
workflow.add_edge("audit", END)

app = workflow.compile()
