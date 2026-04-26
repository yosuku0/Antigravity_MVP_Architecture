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
from pathlib import Path
from typing import Any

import sys
from importlib.util import find_spec

# Add project root to path before local imports
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from domains.knowledge_os import KnowledgeOS
from utils.logging_config import get_logger

logger = get_logger("graph")

from apps.runtime.state import State
from apps.runtime.nodes.plan_executor import plan_executor
from apps.runtime.nodes.run_executor import run_executor
from scripts.audit import scan_secrets
from utils.atomic_io import read_frontmatter, write_frontmatter

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver as Checkpointer
    except ImportError:
        from langgraph.checkpoint.memory import MemorySaver as Checkpointer
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

# ── Node Functions ────────────────────────────────────────────────────

def load_job(state: State) -> State:
    """Read JOB file, extract frontmatter + body."""
    job_path = state["job_path"]
    if not job_path.exists():
        return {**state, "status": "failed", "error": f"JOB not found: {job_path}"}

    try:
        # Parse YAML frontmatter
        fm, body = read_frontmatter(job_path)
    except Exception as e:
        return {**state, "status": "failed", "error": f"Read error: {e}"}

    state["job_id"] = job_path.stem
    state["target_domain"] = fm.get("domain", "")
    state["domain"] = state["target_domain"] # Sync for KnowledgeOS
    
    state["routing_context"] = body[:2000]  # Truncate for routing
    state["review_count"] = 0 # Initialize loop counter
    state["review_feedback"] = None
    state["artifact_path"] = None
    state["planned_objective"] = None
    state["error"] = None
    state["audit_result"] = "pending"
    state["parallel"] = fm.get("parallel", False)

    # HITL Context Recovery
    fm_status = fm.get("status", "created")
    if fm_status == "approved_gate_3":
        state["status"] = "approved_gate_3"
        # Recover artifact path from disk
        staging_path = Path("work/artifacts/staging") / f"{state['job_id']}.md"
        if staging_path.exists():
            state["artifact_path"] = staging_path
    elif "_rejected" in fm_status:
        # Recovery from rejection
        state["status"] = "review_rejected"
        # Extract feedback from body (look for the last ## Reject Feedback header)
        feedback_match = re.findall(r"## Reject Feedback \(Gate \d\)\s*(.*?)(?:\n\n##|$)", body, re.DOTALL)
        if feedback_match:
            state["review_feedback"] = feedback_match[-1].strip()
            # Capture for self-evolution
            try:
                from domains.feedback_memory import get_feedback_memory
                memory = get_feedback_memory()
                memory.add_lesson(
                    task_description=body[:1000], # Task context
                    feedback=state["review_feedback"],
                    job_id=state["job_id"]
                )
            except Exception as e:
                logger.warning(f"Failed to record lesson: {e}", extra={"job_id": state["job_id"]})
        else:
            state["review_feedback"] = "Rejected by operator without specific feedback."
    else:
        state["status"] = "routing"

    logger.info(f"Loaded job {state['job_id']} with status {fm_status}", extra={"job_id": state["job_id"]})
    return state


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
        except Exception as e:
            logger.warning(f"Domain leakage check failed: {e}", extra={"job_id": state.get("job_id")})

    if issues:
        audit_result = f"FAIL: {'; '.join(issues)}"
        return {
            **state,
            "audit_result": audit_result,
            "status": "audit_failed",
            "error": audit_result,
        }

    new_status = "audit_passed"
    
    # Disk Sync: Update physical JOB file
    try:
        fm, body = read_frontmatter(state["job_path"])
        fm["status"] = new_status
        write_frontmatter(state["job_path"], fm, body)
    except Exception as e:
        logger.error(f"Disk Sync failed: {e}", exc_info=True, extra={"job_id": state.get("job_id")})
        # If disk sync fails, the job cannot be resumed correctly.
        return {**state, "status": "failed", "error": f"Disk Sync failed: {e}"}

    logger.info(f"Audit passed for {state['job_id']}", extra={"job_id": state["job_id"]})
    return {
        **state,
        "audit_result": "PASS",
        "status": new_status,
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
        logger.info(f"Promoted {job_id} to {domain} wiki", extra={"job_id": job_id})
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
    builder.add_conditional_edges(
        "load_job",
        lambda state: (
            "promote" if state.get("status") == "approved_gate_3"
            else "plan_executor" if state.get("status") == "review_rejected"
            else "squad_router"
        ),
        {"promote": "promote", "plan_executor": "plan_executor", "squad_router": "squad_router"}
    )

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

    builder.add_edge("audit", END)
    builder.add_edge("promote", END)

    # Checkpointing for resilience
    if LANGGRAPH_AVAILABLE:
        try:
            # Check if it's SqliteSaver which needs from_conn_string
            if hasattr(Checkpointer, "from_conn_string"):
                checkpoint_path = Path(checkpoint_db)
                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                checkpointer = Checkpointer.from_conn_string(str(checkpoint_path))
                # Enable WAL mode for parallel HITL performance
                checkpointer.conn.execute("PRAGMA journal_mode=WAL;")
                checkpointer.conn.execute("PRAGMA synchronous=NORMAL;")
                # Set connection timeout
                checkpointer.conn.execute("PRAGMA busy_timeout = 30000;")
            else:
                # MemorySaver or similar
                checkpointer = Checkpointer()
            return builder.compile(checkpointer=checkpointer)
        except Exception as e:
            logger.warning(f"Checkpointing initialization failed, running without persistence: {e}")
            return builder.compile()

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
