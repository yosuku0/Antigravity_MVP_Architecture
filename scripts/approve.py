#!/usr/bin/env python3
"""CLI tool to approve jobs at HITL gates."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.atomic_io import atomic_write

def approve_gate_1(job_path: Path, approver: str = "higurashi") -> None:
    """Approve a job at Gate 1: transition from CREATED to APPROVED_GATE_1."""
    text = job_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("No frontmatter found")
    
    _, rest = text.split("---", 1)
    yaml_part, body = rest.split("---", 1)
    frontmatter = yaml.safe_load(yaml_part) or {}
    
    status = frontmatter.get("status")
    if status != "created":
        raise ValueError(f"Job status is {status}, expected 'created'")
    
    frontmatter["status"] = "approved_gate_1"
    frontmatter["approved_by"] = approver
    frontmatter["approved_at"] = datetime.now(timezone.utc).isoformat()
    
    yaml_text = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
    content = f"---\n{yaml_text}---\n\n{body.strip()}\n"
    atomic_write(job_path, content)
    print(f"Gate 1 approved: {job_path.name} by {approver}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Approve jobs at HITL gates")
    parser.add_argument("--job", required=True, help="Path to JOB file")
    parser.add_argument("--gate", type=int, required=True, choices=[1, 2, 3], help="Gate number")
    parser.add_argument("--by", default="higurashi", dest="approver", help="Approver name")
    args = parser.parse_args()
    
    job_path = Path(args.job)
    if not job_path.exists():
        print(f"ERROR: Job file not found: {job_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.gate == 1:
            approve_gate_1(job_path, args.approver)
        else:
            print(f"Gate {args.gate} approval not yet implemented (placeholder)", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
