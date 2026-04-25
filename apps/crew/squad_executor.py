#!/usr/bin/env python3
"""Squad executor — instantiates CrewAI squads based on routing context."""
from pathlib import Path
import yaml
from crewai import Crew, Agent, Task

SQUAD_DIR = Path(__file__).resolve().parent / "squads"

def load_squad_config(squad_name: str):
    """Load roles.yaml and tasks.yaml for a squad."""
    squad_path = SQUAD_DIR / squad_name
    with open(squad_path / "roles.yaml") as f:
        roles = yaml.safe_load(f)
    with open(squad_path / "tasks.yaml") as f:
        tasks = yaml.safe_load(f)
    return roles, tasks

def execute_squad(squad_name: str, llm, objective: str, artifact_path: Path) -> dict:
    """Execute a squad with the given LLM and objective."""
    roles, tasks_cfg = load_squad_config(squad_name)
    
    # Create agents
    agents = {}
    for role_key, role_def in roles.items():
        agents[role_key] = Agent(
            role=role_def["role"],
            goal=role_def["goal"],
            backstory=role_def["backstory"],
            allow_delegation=role_def.get("allow_delegation", False),
            verbose=role_def.get("verbose", True),
            llm=llm,
        )
    
    # Create tasks
    task_list = []
    for task_key, task_def in tasks_cfg.items():
        task_list.append(Task(
            description=task_def["description"].format(
                objective=objective,
                output_path=str(artifact_path),
                artifact_path=str(artifact_path),
            ),
            expected_output=task_def["expected_output"],
            agent=agents[task_def["agent"]],
            output_file=str(artifact_path) if "{output_path}" in task_def["description"] else None,
        ))
    
    # Run crew
    crew = Crew(agents=list(agents.values()), tasks=task_list, verbose=True)
    result = crew.kickoff()
    
    # Optional sandbox verification for coding squad
    if squad_name == "coding_squad":
        from apps.runtime.sandbox_executor import execute_artifact_safely
        verification = execute_artifact_safely(artifact_path)
        if not verification.get("skipped"):
            if not verification["success"]:
                # We log but don't necessarily crash the whole thing if sandbox fails 
                # (though the prompt says 'raise RuntimeError', I'll follow it)
                print(f"[sandbox] CRITICAL: Verification failed: {verification.get('stderr')}")
                raise RuntimeError(f"Artifact failed sandbox execution: {verification.get('stderr')}")
            print(f"[sandbox] Verification result: {verification}")
        else:
            print(f"[sandbox] Verification skipped: {verification['reason']}")

    return {
        "result": str(result),
        "artifact_path": str(artifact_path),
    }
