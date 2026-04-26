from pathlib import Path
from apps.runtime.state import State

def plan_executor(state: State) -> State:
    """Construct the objective for squads, injecting feedback if available."""
    job_path = state.get("job_path")
    review_feedback = state.get("review_feedback")
    
    # Construct objective from job_path (or routing_context fallback)
    if job_path and Path(job_path).exists():
        content = Path(job_path).read_text(encoding="utf-8")
    else:
        content = state.get("routing_context", "")
    
    objective = content
    if review_feedback:
        objective = f"{content}\n\n=== PREVIOUS REVIEW FEEDBACK ===\n{review_feedback}\n=== END FEEDBACK ===\n"
    
    return {
        **state,
        "planned_objective": objective,
        "status": "executing",
        "review_feedback": None,  # Clear feedback after consumption
    }
