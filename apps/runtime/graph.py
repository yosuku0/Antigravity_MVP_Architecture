import json
import subprocess
from typing import TypedDict, Optional
from pathlib import Path
from datetime import datetime, timezone
from langgraph.graph import StateGraph, END
import sys
import yaml
from crewai import Crew, Agent, Task

# Ensure utils can be imported
sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.atomic_io import read_frontmatter
from apps.llm_router.complexity_scorer import classify_task
from apps.llm_router.router import LLMRouter

class State(TypedDict):
    job_id: str
    job_path: str
    status: str          # From frontmatter
    routing_context: str # "classify_local" for MVP
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
    }

def crew_execute_node(state: State) -> State:
    """Execute a single CrewAI crew to implement the job objective."""
    # Load config
    repo_root = Path(__file__).resolve().parents[2]
    config_dir = repo_root / "apps" / "crew" / "config"
    with open(config_dir / "roles.yaml", "r", encoding="utf-8") as f:
        roles = yaml.safe_load(f)
    with open(config_dir / "tasks.yaml", "r", encoding="utf-8") as f:
        tasks = yaml.safe_load(f)
    
    # Get LLM from router
    router = LLMRouter()
    llm = router.get_llm(state["routing_context"])
    
    # Create agent
    dev_role = roles["developer"]
    developer = Agent(
        role=dev_role["role"],
        goal=dev_role["goal"],
        backstory=dev_role["backstory"],
        allow_delegation=dev_role.get("allow_delegation", False),
        verbose=dev_role.get("verbose", True),
        llm=llm
    )
    
    # Extract objective from job frontmatter
    job_path = Path(state["job_path"])
    text = job_path.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, rest = text.split("---", 1)
        yaml_part, _ = rest.split("---", 1)
        frontmatter = yaml.safe_load(yaml_part) or {}
        objective = frontmatter.get("objective", "Implement requested feature")
    else:
        objective = "Implement requested feature"

    # Create task
    task_cfg = tasks["implement_task"]
    job_id = state["job_id"]
    artifact_dir = repo_root / "memory" / "working" / job_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "artifact.py"
    
    task = Task(
        description=task_cfg["description"].format(
            objective=objective,
            output_path=str(artifact_path)
        ),
        expected_output=task_cfg["expected_output"],
        agent=developer,
        output_file=str(artifact_path)
    )
    
    # Run crew
    crew = Crew(agents=[developer], tasks=[task], verbose=True)
    result = crew.kickoff()
    
    return {
        **state,
        "artifact_path": str(artifact_path),
        "crew_result": str(result)
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
workflow.add_node("crew_execute", crew_execute_node)
workflow.add_node("audit", audit_node)

workflow.set_entry_point("load_job")
workflow.add_edge("load_job", "router")
workflow.add_edge("router", "crew_execute")
workflow.add_edge("crew_execute", "audit")
workflow.add_edge("audit", END)

app = workflow.compile()
