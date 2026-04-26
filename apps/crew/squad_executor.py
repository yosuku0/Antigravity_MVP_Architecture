#!/usr/bin/env python3
"""Squad executor — instantiates CrewAI squads based on routing context."""
from pathlib import Path
import yaml
try:
    from crewai import Crew, Agent, Task
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    Crew, Agent, Task = None, None, None

SQUAD_DIR = Path(__file__).resolve().parent / "squads"

def load_squad_config(squad_name: str):
    """Load roles.yaml and tasks.yaml for a squad."""
    squad_path = SQUAD_DIR / squad_name
    with open(squad_path / "roles.yaml") as f:
        roles = yaml.safe_load(f)
    with open(squad_path / "tasks.yaml") as f:
        tasks = yaml.safe_load(f)
    return roles, tasks

def execute_squad(squad_name: str, llm, objective: str, artifact_path: Path, domain: str | None = None) -> dict:
    """Execute a squad. Checks for crew.py first, falls back to roles/tasks YAML."""
    squad_dir = SQUAD_DIR / squad_name
    crew_py = squad_dir / "crew.py"
    
    # 1. Try dynamic loading from crew.py
    if crew_py.exists():
        result = _execute_squad_from_config(crew_py, objective, domain, llm)
    else:
        # 2. Fallback to roles.yaml / tasks.yaml
        result = _execute_squad_from_yaml(squad_name, llm, objective, artifact_path)

    # Optional sandbox verification for coding squad
    if squad_name == "coding_squad":
        from apps.runtime.sandbox_executor import execute_artifact_safely
        verification = execute_artifact_safely(artifact_path)
        
        # Tier 3 skip is a warning, not a failure
        if verification.get("tier") == 3:
            print(f"[sandbox] WARN: {verification.get('reason')}")
        elif not verification.get("success", False):
            print(f"[sandbox] CRITICAL: Verification failed: {verification.get('stderr')}")
            raise RuntimeError(f"Artifact failed sandbox execution: {verification.get('stderr')}")
        else:
            print(f"[sandbox] Verification result (tier={verification.get('tier')}): OK")

    return {
        "result": str(result),
        "artifact_path": str(artifact_path),
    }

def _execute_squad_from_config(crew_py: Path, objective: str, domain: str | None, llm) -> str:
    """Dynamically load and execute create_crew() from crew.py."""
    if not CREWAI_AVAILABLE:
        return f"[CrewAI not available - would execute {crew_py}]"
    import importlib.util
    spec = importlib.util.spec_from_file_location("crew_config", crew_py)
    if spec is None or spec.loader is None:
        return "[Failed to load crew config]"

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if hasattr(mod, "create_crew"):
        crew = mod.create_crew(objective=objective, llm=llm, domain=domain)
        return str(crew.kickoff())
    return f"[No create_crew() found in {crew_py}]"

def _execute_squad_from_yaml(squad_name: str, llm, objective: str, artifact_path: Path) -> str:
    """Legacy/Fallback: Load roles.yaml and tasks.yaml for a squad."""
    if not CREWAI_AVAILABLE:
        return f"[CrewAI not available - would execute squad {squad_name} from YAML]"
    roles, tasks_cfg = load_squad_config(squad_name)
    
    # Create agents
    agents = {}
    for role_key, role_def in roles.items():
        agent_tools = []
        if "tools" in role_def:
            for tool_name in role_def["tools"]:
                if tool_name == "web_research":
                    from apps.crew.squads.research_squad.tools.browser_tool import WebResearchTool
                    agent_tools.append(WebResearchTool())
                elif tool_name == "file_read":
                    from crewai_tools import FileReadTool
                    agent_tools.append(FileReadTool())

        agents[role_key] = Agent(
            role=role_def["role"],
            goal=role_def["goal"],
            backstory=role_def["backstory"],
            allow_delegation=role_def.get("allow_delegation", False),
            verbose=role_def.get("verbose", True),
            llm=llm,
            tools=agent_tools,
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
    return str(crew.kickoff())
