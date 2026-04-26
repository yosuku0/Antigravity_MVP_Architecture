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
    
    # 1. Retrieve past lessons learned (Self-Evolution RAG)
    try:
        from domains.feedback_memory import get_feedback_memory
        memory = get_feedback_memory()
        lessons = memory.search_lessons(content[:2000]) # Use context as query
        if lessons:
            lesson_block = "\n\n### IMPORTANT: Past Lessons Learned (Avoid these mistakes)\n"
            for i, lesson in enumerate(lessons, 1):
                lesson_block += f"{i}. {lesson}\n"
            objective = f"{lesson_block}\n{objective}"
    except Exception as e:
        from utils.logging_config import get_logger
        get_logger("plan_executor").warning(f"Failed to retrieve lessons: {e}")

    # 2. Inject current review feedback if in correction loop
    if review_feedback:
        objective = f"{objective}\n\n=== CURRENT REVIEW FEEDBACK ===\n{review_feedback}\n=== END FEEDBACK ===\n"
    
    return {
        **state,
        "planned_objective": objective,
        "status": "executing",
        "review_feedback": None,  # Clear feedback after consumption
    }
