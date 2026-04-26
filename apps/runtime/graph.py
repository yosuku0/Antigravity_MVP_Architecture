"""
graph.py — LangGraph orchestrator with domain-aware squad routing

Graph structure:
    load_job → squad_router → plan_executor → run_executor → brain_review → audit → promote → END

    Feedback loop (L2, max 3 iterations):
        brain_review --(failed, count<3)--> plan_executor

Domain awareness:
  - JOB YAML frontmatter specifies target_domain (game|market|personal)
  - squad_router filters squads by domain permissions (.domain allowed_squads)
  - plan_executor constructs objective with optional review_feedback injection
  - run_executor executes squads via apps.crew.squad_executor
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

from apps.runtime.state import State
from apps.runtime.nodes.plan_executor import plan_executor
from apps.runtime.nodes.run_executor import run_executor
from scripts.audit import scan_secrets


# ── State Schema ──────────────────────────────────────────────────────

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

    state["job_id"] = job_path.stem
    state["target_domain"] = frontmatter.get("domain", "")
    state["domain"] = state["target_domain"] # Sync for KnowledgeOS
    
    body = parts[2].strip() if text.startswith("---") and len(parts) >= 3 else text
    state["routing_context"] = body[:2000]  # Truncate for routing
    state["review_count"] = 0 # Initialize loop counter
    state["review_feedback"] = None
    state["artifact_path"] = None
    state["planned_objective"] = None
    state["error"] = None
    state["audit_result"] = "pending"
    state["parallel"] = frontmatter.get("parallel", False)

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
        findings = scan_secrets(content)
        for f in findings:
            issues.append(f"Potential secret found: {f['description']} ({f['match']})")
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


# Node aliases and additional nodes
audit_node = audit

def promote_to_wiki(state: State) -> State:
    """Promote artifact to domain wiki via KnowledgeOS."""
    artifact_path = state.get("artifact_path")
    domain = state.get("target_domain")
    job_id = state.get("job_id", "unknown")

    if not artifact_path or not artifact_path.exists():
        return {**state, "status": "failed", "error": "Artifact missing at promote"}

    try:
        from domains.knowledge_os import KnowledgeOS
        content = artifact_path.read_text(encoding="utf-8")
        kos = KnowledgeOS()
        kos.save(
            domain=domain,
            topic=f"job_{job_id}",
            content=content,
            frontmatter={"job_id": job_id, "promoted_from": str(artifact_path)},
        )
        return {**state, "status": "promoted", "error": None}
    except Exception as e:
        return {**state, "status": "failed", "error": f"Promote failed: {e}"}


# ── Graph Builder ─────────────────────────────────────────────────────

def build_graph(checkpoint_db: str = "work/checkpoints.db") -> StateGraph:
    """Build and compile the LangGraph state machine."""
    builder = StateGraph(State)

    builder.add_node("load_job", load_job)
    builder.add_node("squad_router", squad_router)
    builder.add_node("plan_executor", plan_executor)
    builder.add_node("run_executor", run_executor)
    builder.add_node("brain_review", brain_review)
    builder.add_node("audit", audit_node)
    builder.add_node("promote", promote_to_wiki)

    # Add Edges
    builder.set_entry_point("load_job")
    builder.add_edge("load_job", "squad_router")

    # Squad Router condition
    builder.add_conditional_edges(
        "squad_router",
        lambda state: "plan_executor" if state.get("status") == "executing" else "failed",
        {"plan_executor": "plan_executor", "failed": END}
    )

    # Core Execution Loop
    builder.add_edge("plan_executor", "run_executor")
    builder.add_edge("run_executor", "brain_review")

    # Review Loop (L2)
    builder.add_conditional_edges(
        "brain_review",
        lambda state: (
            "audit" if state.get("status") == "auditing"
            else "plan_executor" if state.get("status") == "reviewing" and state.get("review_count", 0) < 3
            else "failed"
        ),
        {
            "audit": "audit",
            "plan_executor": "plan_executor",
            "failed": END,
        }
    )

    builder.add_edge("audit", "promote")
    builder.add_edge("promote", END)

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
        "planned_objective": None,
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
