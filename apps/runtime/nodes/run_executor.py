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
    
    # 루ープ前に staging パスを1回だけ作成
    staging_dir = Path("work/artifacts/staging")
    staging_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = staging_dir / f"{job_id}.md"

    results = []
    for squad_name in squads:
        try:
            res = execute_squad(squad_name, llm, objective, artifact_path, domain=target_domain)
            results.append(f"### {squad_name}\n{res['result']}")
        except Exception as e:
            results.append(f"### {squad_name}\nERROR: {e}")
    
    # 1回だけ最終書き込み
    artifact_path.write_text("\n\n".join(results), encoding="utf-8")
    
    return {
        **state,
        "status": "reviewing",
        "artifact_path": artifact_path,
    }
