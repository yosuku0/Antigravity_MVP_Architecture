import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from apps.runtime.state import State
from apps.crew.squad_executor import execute_squad

def run_executor(state: State) -> State:
    """Execute the squads sequentially or in parallel based on the parallel flag."""
    squads = state.get("squads", [])
    target_domain = state.get("target_domain")
    objective = state.get("planned_objective", "")
    job_id = state["job_id"]
    parallel = state.get("parallel", False)
    
    # Get LLM from unified router
    try:
        from apps.llm_router.router import UnifiedRouter
        router = UnifiedRouter()
        llm = router.get_llm("nim_cheap")
    except Exception:
        llm = None
    
    staging_dir = Path("work/artifacts/staging")
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    if parallel and len(squads) > 1:
        return _run_parallel(squads, llm, objective, job_id, target_domain, staging_dir, state)
    else:
        return _run_sequential(squads, llm, objective, job_id, target_domain, staging_dir, state)


def _run_sequential(squads, llm, objective, job_id, target_domain, staging_dir, state) -> State:
    """Standard sequential execution."""
    artifact_path = staging_dir / f"{job_id}.md"
    results = []
    for squad_name in squads:
        try:
            res = execute_squad(squad_name, llm, objective, artifact_path, domain=target_domain)
            results.append(f"### {squad_name}\n{res['result']}")
        except Exception as e:
            results.append(f"### {squad_name}\nERROR: {e}")
    
    # 最終書き込み
    artifact_path.write_text("\n\n".join(results), encoding="utf-8")
    
    return {
        **state,
        "status": "reviewing",
        "artifact_path": artifact_path,
    }


def _run_parallel(squads, llm, objective, job_id, target_domain, staging_dir, state) -> State:
    """Parallel execution with isolated temporary artifacts."""
    def run_one(squad_name: str) -> tuple[str, str]:
        temp_path = staging_dir / f"{job_id}_{squad_name}.md"
        try:
            res = execute_squad(squad_name, llm, objective, temp_path, domain=target_domain)
            return (squad_name, f"### {squad_name}\n{res['result']}")
        except Exception as e:
            return (squad_name, f"### {squad_name}\nERROR: {e}")

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_map = {
            executor.submit(run_one, name): name for name in squads
        }
        results = []
        for future in concurrent.futures.as_completed(future_map):
            squad_name, output = future.result()
            # squads.index(squad_name) を使って元の順序を保持
            results.append((squads.index(squad_name), output))
    
    # 元のsquad順に並べ替え
    results.sort(key=lambda x: x[0])
    final_text = "\n\n".join([r[1] for r in results])
    
    final_path = staging_dir / f"{job_id}.md"
    final_path.write_text(final_text, encoding="utf-8")
    
    return {
        **state,
        "status": "reviewing",
        "artifact_path": final_path,
    }
