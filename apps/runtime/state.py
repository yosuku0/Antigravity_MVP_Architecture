from pathlib import Path
from typing import TypedDict

class State(TypedDict):
    # Core identifying fields
    job_id: str
    job_path: Path
    domain: str
    target_domain: str
    squads: list[str]
    
    # Execution state
    status: str
    audit_result: str
    error: str | None
    
    # Feedback loop (L2)
    review_feedback: str | None
    review_count: int
    artifact_path: Path | None
    
    # Phase D fields
    planned_objective: str | None
    routing_context: str | None
