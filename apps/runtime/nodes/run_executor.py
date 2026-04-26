from pathlib import Path
from apps.runtime.state import State
from apps.crew.squad_executor import execute_squad

def run_executor(state: State) -> State:
    """Execute the squads sequentially based on the planned objective."""
    squads = state.get("squads", [])
    target_domain = state.get("target_domain")
    objective = state.get("planned_objective", "")
    job_id = state["job_id"]
    
    # Get LLM from unified router
    try:
        from apps.llm_router.router import UnifiedRouter
        router = UnifiedRouter()
        llm = router.get_llm("nim_cheap")
    except Exception:
        llm = None
    
    results = []
    for squad_name in squads:
        try:
            # We use a temporary artifact path for staging
            staging_dir = Path("work/artifacts/staging")
            staging_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = staging_dir / f"{job_id}.md"
            
            res = execute_squad(squad_name, llm, objective, artifact_path, domain=target_domain)
            results.append(f"### {squad_name}\n{res['result']}")
        except Exception as e:
            results.append(f"### {squad_name}\nERROR: {e}")
    
    # Final staging artifact consolidation
    final_artifact_path = Path(f"work/artifacts/staging/{job_id}.md")
    final_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    final_artifact_path.write_text("\n\n".join(results), encoding="utf-8")
    
    return {
        **state,
        "status": "reviewing",
        "artifact_path": final_artifact_path,
    }
