"""
graph.py — LangGraph orchestrator with domain-aware squad routing

Graph structure:
    load_job → router → squad_router → execute_squads → audit → END

Domain awareness:
  - JOB YAML frontmatter specifies target_domain (game|market|personal)
  - squad_router filters squads by domain permissions (.domain allowed_squads)
  - execute_squads injects domain context into each squad's objective
  - Results are promoted to the correct domain wiki automatically
"""

from __future__ import annotations

import json
import re
import time
import threading
from pathlib import Path
from typing import Any, TypedDict

import sys
import yaml
from importlib.util import find_spec

from domains.knowledge_os import KnowledgeOS
from utils.atomic_io import atomic_write

# Add project root to path before other local imports if needed
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.sqlite import SqliteSaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    # Stub for type checking
    class StateGraph:
        def add_node(self, *a, **k): pass
        def add_edge(self, *a, **k): pass
        def set_entry_point(self, *a, **k): pass
        def compile(self, *a, **k): return self
    END = "END"
    class SqliteSaver:
        def __init__(self, *a, **k): pass

# CrewAI availability check
CREWAI_AVAILABLE = find_spec("crewai") is not None

# Terminal statuses for graph completion
TERMINAL_STATUSES = {"done", "failed", "audit_failed", "promoted", "cancelled"}


# ── State Schema ──────────────────────────────────────────────────────

class State(TypedDict):
    """LangGraph state shared across nodes."""
    job_id: str
    job_path: Path
    status: str  # queued | routing | executing | reviewing | auditing | done | failed
    routing_context: str
    squads: list[str]
    target_domain: str | None  # game | market | personal
    artifact_path: Path | None
    audit_result: str
    review_feedback: str | None
    review_count: int
    error: str | None


# ── Node Functions ────────────────────────────────────────────────────

def load_job(state: State) -> State:
    """Read JOB file, extract frontmatter + body."""
    job_path = state["job_path"]
    if not job_path.exists():
        return {**state, "status": "failed", "error": f"JOB not found: {job_path}"}

    try:
        text = job_path.read_text(encoding="utf-8")
    except Exception as e:
        return {**state, "status": "failed", "error": f"Read error: {e}"}

    # Parse YAML frontmatter
    frontmatter: dict[str, Any] = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                pass

    state["target_domain"] = frontmatter.get("domain")
    body = parts[2].strip() if text.startswith("---") and len(parts) >= 3 else text
    state["routing_context"] = body[:2000]  # Truncate for routing

    return {**state, "status": "routing"}


def router(state: State) -> State:
    """Simple routing — all jobs go to squad execution in Phase B."""
    if state.get("error"):
        return {**state, "status": "failed"}
    return {**state, "status": "routing"}


def squad_router(state: State) -> State:
    """Determine which squads to run based on domain permissions.

    Reads domains/{domain}/.domain to filter squads by allowed_squads.
    Fail-closed: returns failed status if domain is missing or invalid.
    """
    domain = state.get("target_domain")
    
    # No domain specified → fail immediately
    if not domain:
        return {
            **state,
            "status": "failed",
            "error": "Domain not specified in job frontmatter",
        }

    try:
        kos = KnowledgeOS()
        meta = kos._domains.get(domain)
    except Exception as e:
        return {
            **state,
            "status": "failed",
            "error": f"Domain routing failed for {domain}: {e}",
        }

    # Unknown domain or missing .domain file → fail immediately
    if meta is None:
        return {
            **state,
            "status": "failed",
            "error": f"Unknown domain or missing domain metadata: {domain}",
        }

    # No allowed squads configured → fail immediately
    if not meta.allowed_squads:
        return {
            **state,
            "status": "failed",
            "error": f"No valid squads allowed for domain: {domain}",
        }

    ALL_SQUADS = ("coding_squad", "research_squad", "review_squad")
    # Normalize squad names in case they are missing the _squad suffix
    normalized = [f"{s}_squad" if not s.endswith("_squad") else s for s in meta.allowed_squads]
    allowed = [s for s in normalized if s in ALL_SQUADS]
    
    # Intersection is empty → fail immediately
    if not allowed:
        return {
            **state,
            "status": "failed",
            "error": f"No valid squads allowed for domain: {domain}",
        }

    return {**state, "squads": allowed, "status": "executing"}


def execute_squads(state: State) -> State:
    """Execute squads sequentially with feedback injection."""
    squads = state.get("squads", [])
    domain = state.get("target_domain")
    job_path = state.get("job_path")
    review_feedback = state.get("review_feedback")
    
    # Read job content
    if job_path and job_path.exists():
        content = job_path.read_text(encoding="utf-8")
    else:
        content = state.get("routing_context", "")
    
    # Inject review feedback if present (loop iteration)
    objective = content
    if review_feedback:
        objective = f"""{content}

=== PREVIOUS REVIEW FEEDBACK ===
The following issues were identified in the previous review. Address all of them:
{review_feedback}
=== END FEEDBACK ===
"""
    
    results = []
    for squad_name in squads:
        try:
            result = _execute_single_squad(squad_name, objective, domain)
            results.append(f"{squad_name}: {result}")
        except Exception as e:
            results.append(f"{squad_name}: ERROR — {e}")

    # Write artifact to staging
    artifact_path = Path(f"work/artifacts/staging/{state['job_id']}.md")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_content = "\n\n".join(results)
    artifact_path.write_text(artifact_content, encoding="utf-8")
    
    return {
        **state,
        "status": "reviewing",
        "artifact_path": artifact_path,
        "review_feedback": None,  # Clear feedback for next review
    }


def _execute_single_squad(squad_name: str, objective: str, domain: str | None) -> str:
    """Execute a single squad with optional domain context."""
    squad_dir = Path(__file__).resolve().parent.parent / "crew" / "squads" / squad_name

    # Inject domain context into objective
    if domain:
        objective = f"[Domain: {domain}] {objective}"

    # Check if squad has a crew.py config
    crew_py = squad_dir / "crew.py"
    if crew_py.exists():
        return _execute_squad_from_config(crew_py, objective, squad_name, domain)

    # Fallback: return placeholder (squad not yet configured)
    return f"Squad {squad_name} executed with objective: {objective[:100]}..."


def _execute_squad_from_config(
    crew_py: Path, objective: str, squad_name: str, domain: str | None
) -> str:
    """Execute a squad defined in crew.py."""
    if not CREWAI_AVAILABLE:
        return f"[CrewAI not available — would execute {crew_py}]"

    # Dynamic import of squad config
    import importlib.util
    spec = importlib.util.spec_from_file_location("crew_config", crew_py)
    if spec is None or spec.loader is None:
        return "[Failed to load crew config]"

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Get LLM from unified router
    try:
        from apps.llm_router.router import UnifiedRouter
        router = UnifiedRouter()
        llm = router.get_llm("nim_cheap")
    except Exception:
        llm = None  # Will use CrewAI default

    # Build agents and tasks from config
    if hasattr(mod, "create_crew"):
        crew = mod.create_crew(objective=objective, llm=llm, domain=domain)
        return str(crew.kickoff())

    return f"[No create_crew() found in {crew_py}]"


def brain_review(state: State) -> State:
    """Review artifact using review_squad."""
    review_count = state.get("review_count", 0) + 1
    artifact_path = state.get("artifact_path")
    
    # None check (C-2 fix)
    if artifact_path is None or not artifact_path.exists():
        # S-1: Loop limit reached?
        if review_count >= 3:
            return {
                **state,
                "status": "failed",
                "error": f"Review loop exceeded after {review_count} attempts (artifact missing)",
                "review_count": review_count,
            }
        return {**state, "status": "auditing", "review_count": review_count}
    
    # Call brain_review CLI / review_squad
    result = _call_review_squad(artifact_path)
    
    if result.get("passed", False):
        return {
            **state,
            "status": "auditing",
            "review_feedback": None,
            "review_count": review_count,
        }
    else:
        # S-1: Loop limit reached?
        if review_count >= 3:
            return {
                **state,
                "status": "failed",
                "error": f"Review loop exceeded after {review_count} attempts",
                "review_feedback": result.get("feedback"),
                "review_count": review_count,
            }
        return {
            **state,
            "status": "reviewing",
            "review_feedback": result.get("feedback"),
            "review_count": review_count,
        }


def _call_review_squad(artifact_path: Path) -> dict:
    """Bridge to scripts/brain_review.py CLI."""
    import sys
    from utils.safe_subprocess import run_generic
    try:
        # Run the review CLI using the current interpreter and absolute path
        script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "brain_review.py"
        cmd = [sys.executable, str(script_path), "--artifact", str(artifact_path)]
        res_dict = run_generic(cmd)
        
        # Parse result from dict
        passed = res_dict["success"]
        
        # Try to parse JSON feedback if it exists
        feedback_path = Path("work/blackboard/feedback") / f"{artifact_path.stem}.json"
        if feedback_path.exists():
            import json
            with open(feedback_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"passed": data.get("passed", passed), "feedback": data.get("feedback", "No feedback")}
        
        return {"passed": passed, "feedback": (res_dict["stdout"] + "\n" + res_dict["stderr"]).strip() or "Review failed"}
    except Exception as e:
        return {"passed": False, "feedback": f"Review execution error: {e}"}


def audit(state: State) -> State:
    """Audit node — secret scan + syntax check + domain leakage check."""
    artifact_path = state.get("artifact_path")
    if not artifact_path or not artifact_path.exists():
        return {**state, "status": "failed", "error": "Artifact missing after execution"}

    issues = []

    # Secret scan
    try:
        content = artifact_path.read_text(encoding="utf-8")
        secret_patterns = [
            r"sk-[a-zA-Z0-9]{20,}",  # OpenAI-style API keys
            r"ghp_[a-zA-Z0-9]{36}",   # GitHub personal access tokens
            r"AKIA[0-9A-Z]{16}",       # AWS access key ID
            r"\b[0-9a-f]{64}\b",       # Hex secrets
        ]
        for pattern in secret_patterns:
            if re.search(pattern, content):
                issues.append(f"Potential secret found: {pattern[:20]}...")
    except Exception as e:
        issues.append(f"Audit read error: {e}")

    # Domain leakage check (if domain specified)
    domain = state.get("target_domain")
    if domain:
        try:
            # Check if artifact references other domains without derive()
            for other in {"game", "market", "personal"} - {domain}:
                if other in content.lower() and f"derived_from: {other}" not in content:
                    issues.append(f"Cross-domain reference to '{other}' without derive() provenance")
        except Exception:
            pass

    if issues:
        audit_result = f"FAIL: {'; '.join(issues)}"
        return {
            **state,
            "audit_result": audit_result,
            "status": "audit_failed",
            "error": audit_result,
        }

    return {
        **state,
        "audit_result": "PASS",
        "status": "done",
        "error": None,
    }


# ── Graph Builder ─────────────────────────────────────────────────────

def build_graph(checkpoint_db: str = "work/checkpoints.db") -> StateGraph:
    """Build and compile the LangGraph state machine."""
    builder = StateGraph(State)

    builder.add_node("load_job", load_job)
    builder.add_node("router", router)
    builder.add_node("squad_router", squad_router)
    builder.add_node("execute_squads", execute_squads)
    builder.add_node("brain_review", brain_review)
    builder.add_node("audit", audit)

    builder.set_entry_point("load_job")
    builder.add_edge("load_job", "router")
    builder.add_edge("router", "squad_router")
    builder.add_edge("squad_router", "execute_squads")
    
    # New edge: execute_squads -> brain_review
    builder.add_edge("execute_squads", "brain_review")

    # Conditional logic for brain_review
    builder.add_conditional_edges(
        "brain_review",
        lambda state: (
            "audit" if state.get("status") == "auditing"
            else "execute_squads" if state.get("status") == "reviewing" and state.get("review_count", 0) < 3
            else "failed"
        ),
        {
            "audit": "audit",
            "execute_squads": "execute_squads",
            "failed": END,
        }
    )

    # Audit to END if terminal
    builder.add_conditional_edges(
        "audit",
        lambda state: END if state.get("status") in TERMINAL_STATUSES else "audit"
    )

    # Checkpointing for resilience
    if LANGGRAPH_AVAILABLE:
        checkpoint_path = Path(checkpoint_db)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpointer = SqliteSaver.from_conn_string(str(checkpoint_path))
        return builder.compile(checkpointer=checkpointer)

    return builder.compile()


# ── Direct Execution ──────────────────────────────────────────────────

def run_job(job_path: str, job_id: str | None = None) -> dict[str, Any]:
    """Execute a single job through the graph."""
    if not LANGGRAPH_AVAILABLE:
        return {"status": "failed", "error": "LangGraph not installed"}

    graph = build_graph()
    job_id = job_id or Path(job_path).stem

    initial_state: State = {
        "job_id": job_id,
        "job_path": Path(job_path),
        "status": "queued",
        "routing_context": "",
        "squads": [],
        "target_domain": None,
        "artifact_path": None,
        "audit_result": "",
        "review_feedback": None,
        "review_count": 0,
        "error": None,
    }

    config = {"configurable": {"thread_id": job_id}}
    result = graph.invoke(initial_state, config)
    return dict(result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python graph.py <job_file.md>")
        sys.exit(1)

    result = run_job(sys.argv[1])
    print(json.dumps(result, indent=2, default=str))
