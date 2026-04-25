#!/usr/bin/env python3
"""
brain_review.py — Trigger review_squad on an artifact and write feedback to blackboard.
Usage:
    python scripts/brain_review.py --artifact work/artifacts/staging/JOB-xxx.md
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BLACKBOARD_DIR = Path("work/blackboard")
FEEDBACK_DIR = BLACKBOARD_DIR / "feedback"
REVIEW_DONE_DIR = BLACKBOARD_DIR / "review_done"


def review_artifact(artifact_path: Path) -> dict:
    """Run review_squad on the given artifact and return review result.
    
    Placeholder implementation — integrates with actual review_squad in Step 2.
    Returns a dict with:
        - passed: bool
        - feedback: str (specific issues found, or "approved")
        - timestamp: str (ISO format)
    """
    # Placeholder: simulate review
    content = artifact_path.read_text(encoding="utf-8")
    
    # Basic checks (placeholder for actual review_squad)
    issues = []
    if len(content) < 100:
        issues.append("Artifact too short")
    if "TODO" in content:
        issues.append("Unresolved TODO found")
    
    passed = len(issues) == 0
    return {
        "passed": passed,
        "feedback": "; ".join(issues) if issues else "approved",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifact": str(artifact_path),
    }


def write_feedback(result: dict, artifact_path: Path) -> None:
    """Write review result to blackboard."""
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DONE_DIR.mkdir(parents=True, exist_ok=True)
    
    feedback_path = FEEDBACK_DIR / f"{artifact_path.stem}.json"
    with open(feedback_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    if result["passed"]:
        # Move artifact to review_done on approval
        done_path = REVIEW_DONE_DIR / artifact_path.name
        done_path.write_text(artifact_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[OK] Artifact approved: {artifact_path.name}")
    else:
        print(f"[REVIEW] Issues found in {artifact_path.name}: {result['feedback']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Trigger review on an artifact")
    parser.add_argument("--artifact", required=True, help="Path to artifact file")
    args = parser.parse_args()
    
    artifact_path = Path(args.artifact)
    if not artifact_path.exists():
        print(f"[ERROR] Artifact not found: {artifact_path}")
        return 1
    
    result = review_artifact(artifact_path)
    write_feedback(result, artifact_path)
    
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
