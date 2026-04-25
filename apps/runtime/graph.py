import json
import subprocess
from typing import TypedDict, Optional, List
from pathlib import Path
from datetime import datetime, timezone
from langgraph.graph import StateGraph, END
import sys
import yaml
from crewai import Crew, Agent, Task

# Ensure utils can be imported
sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.atomic_io import read_frontmatter, write_frontmatter
from apps.llm_router.complexity_scorer import classify_task
from apps.llm_router.router import LLMRouter

class State(TypedDict):
    job_id: str
    job_path: str
    status: str          # From frontmatter
    routing_context: str # "classify_local" for MVP
    squads: List[str]    # List of squads to execute
    objective: str       # Job objective
    artifact_path: str   # Path to generated artifact
    audit_result: Optional[str] # "pass", "fail", or None
    audit_errors: Optional[str]
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
    """Classify task and set routing_context."""
    job_path = Path(state["job_path"])
    frontmatter, body = read_frontmatter(job_path)
    objective = frontmatter.get("objective", body.split("\n")[0] if body else "Implement requested feature")
    
    classification = classify_task(objective)
    routing_context = classification["recommended_context"]
    
    print(f"[router] Task classified as {classification['level']} → {routing_context}")
    
    return {
        **state,
        "routing_context": routing_context,
        "objective": objective
    }

def squad_router(state: State) -> State:
    """Determine which squad(s) to run based on routing_context."""
    context = state.get("routing_context", "classify_local")
    
    # Simple mapping: complex tasks get research + coding + review
    if context in ("nim_large", "nim_code", "review"):
        state["squads"] = ["research_squad", "coding_squad", "review_squad"]
    elif context in ("nim_fast", "nim_cheap", "classify_remote"):
        state["squads"] = ["coding_squad", "review_squad"]
    else:
        state["squads"] = ["coding_squad"]  # trivial tasks
    
    return state

def execute_squads_sequential(state: State) -> State:
    """Run squads in sequence (safe for MVP)."""
    from apps.llm_router.router import LLMRouter
    from apps.crew.squad_executor import execute_squad
    
    router = LLMRouter()
    llm = router.get_llm(state["routing_context"])
    
    artifact_dir = Path("memory/working") / state["job_id"]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    last_artifact_path = None
    for squad_name in state["squads"]:
        artifact_path = artifact_dir / f"{squad_name}_artifact.py"
        result = execute_squad(
            squad_name=squad_name,
            llm=llm,
            objective=state.get("objective", "Implement requested feature"),
            artifact_path=artifact_path,
        )
        print(f"[squad] {squad_name} complete: {result['artifact_path']}")
        last_artifact_path = artifact_path
    
    # Final artifact = coding_squad output (or last squad)
    coding_artifact = artifact_dir / "coding_squad_artifact.py"
    final_artifact = coding_artifact if coding_artifact.exists() else last_artifact_path
    
    return {
        **state,
        "artifact_path": str(final_artifact) if final_artifact and final_artifact.exists() else None,
    }

def audit_node(state: State) -> State:
    """Run audit.py on the artifact and set audit_result."""
    path_str = state.get("artifact_path", "")
    if not path_str:
        return {**state, "audit_result": "fail", "audit_errors": "No artifact path"}
        
    artifact_path = Path(path_str)
    
    # Call scripts/audit.py as subprocess
    repo_root = Path(__file__).resolve().parents[2]
    audit_script = repo_root / "scripts" / "audit.py"
    result = subprocess.run(
        [sys.executable, str(audit_script), str(artifact_path)],
        capture_output=True,
        text=True
    )
    
    # 3. Update frontmatter
    job_path = Path(state["job_path"])
    try:
        fm, body = read_frontmatter(job_path)
        fm["audit_result"] = result.stdout.strip().lower()
        if result.stderr:
            fm["audit_errors"] = result.stderr.strip()
        write_frontmatter(job_path, fm, body)
    except Exception as e:
        print(f"Error updating audit frontmatter: {e}")

    # Parse output
    output = result.stdout.strip()
    if output == "PASS":
        return {**state, "audit_result": "pass"}
    else:
        return {**state, "audit_result": "fail", "audit_errors": result.stderr.strip()}

# Graph definition
workflow = StateGraph(State)

workflow.add_node("load_job", load_job_node)
workflow.add_node("router", router_node)
workflow.add_node("squad_router", squad_router)
workflow.add_node("execute_squads", execute_squads_sequential)
workflow.add_node("audit", audit_node)

workflow.set_entry_point("load_job")
workflow.add_edge("load_job", "router")
workflow.add_edge("router", "squad_router")
workflow.add_edge("squad_router", "execute_squads")
workflow.add_edge("execute_squads", "audit")
workflow.add_edge("audit", END)

app = workflow.compile()
