from typing import TypedDict, Annotated
from pathlib import Path
from langgraph.graph import StateGraph, END

class State(TypedDict):
    job_id: str
    job_path: str
    status: str
    routing_context: str
    artifact_path: str

def load_job_node(state: State) -> State:
    # TODO: Read YAML frontmatter from job_path
    state["status"] = "loaded"
    return state

def router_node(state: State) -> State:
    # Always routes to local for MVP placeholder
    # TODO: Implement real routing logic in C-006
    state["routing_context"] = "classify_local"
    return state

def crew_execute_node(state: State) -> State:
    # Dummy artifact writing
    job_id = state.get("job_id", "unknown")
    repo_root = Path(__file__).resolve().parents[2]
    working_dir = repo_root / "memory" / "working" / job_id
    working_dir.mkdir(parents=True, exist_ok=True)
    
    artifact_path = working_dir / "artifact.md"
    artifact_path.write_text("Dummy artifact content", encoding="utf-8")
    
    state["artifact_path"] = str(artifact_path)
    state["status"] = "executed"
    return state

def audit_node(state: State) -> State:
    # Dummy audit
    # TODO: Implement real audit in D-001
    state["status"] = "pass"
    return state

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
