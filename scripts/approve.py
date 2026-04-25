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

def approve_gate_2(job_path: Path, approver: str = "higurashi", reject: bool = False) -> None:
    """Approve or reject a job at Gate 2."""
    text = job_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("No frontmatter found")
        
    _, rest = text.split("---", 1)
    yaml_part, body = rest.split("---", 1)
    frontmatter = yaml.safe_load(yaml_part) or {}
    
    status = frontmatter.get("status")
    # In practice, it might be audit_passed or audit_failed depending on HITL decision
    # But usually Gate 2 is for audit_passed. 
    if status != "audit_passed" and not reject:
        raise ValueError(f"Job status is {status}, expected 'audit_passed' for approval")
    
    if reject:
        frontmatter["status"] = "gate_2_rejected"
        frontmatter["gate_2_rejected_by"] = approver
        frontmatter["gate_2_rejected_at"] = datetime.now(timezone.utc).isoformat()
        print(f"Gate 2 REJECTED: {job_path.name} by {approver}")
    else:
        frontmatter["status"] = "approved_gate_2"
        frontmatter["approved_gate_2_by"] = approver
        frontmatter["approved_gate_2_at"] = datetime.now(timezone.utc).isoformat()
        print(f"Gate 2 approved: {job_path.name} by {approver}")
    
    yaml_text = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
    content = f"---\n{yaml_text}---\n\n{body.strip()}\n"
    atomic_write(job_path, content)

def approve_gate_3(job_path: Path, approver: str = "higurashi") -> None:
    """Approve promotion at Gate 3. (Implemented in B-009)"""
    text = job_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("No frontmatter found")
        
    _, rest = text.split("---", 1)
    yaml_part, body = rest.split("---", 1)
    frontmatter = yaml.safe_load(yaml_part) or {}
    
    if frontmatter.get("status") != "promotion_pending":
        raise ValueError(f"Expected 'promotion_pending', got '{frontmatter.get('status')}'")
    
    frontmatter["status"] = "approved_gate_3"
    frontmatter["approved_gate_3_by"] = approver
    frontmatter["approved_gate_3_at"] = datetime.now(timezone.utc).isoformat()
    
    yaml_text = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
    content = f"---\n{yaml_text}---\n\n{body.strip()}\n"
    atomic_write(job_path, content)
    print(f"Gate 3 approved: {job_path.name} by {approver}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Approve jobs at HITL gates")
    parser.add_argument("--job", required=True, help="Path to JOB file")
    parser.add_argument("--gate", type=int, required=True, choices=[1, 2, 3], help="Gate number")
    parser.add_argument("--by", default="higurashi", dest="approver", help="Approver name")
    parser.add_argument("--reject", action="store_true", help="Reject instead of approve (Gate 2 only)")
    args = parser.parse_args()
    
    job_path = Path(args.job)
    if not job_path.exists():
        print(f"ERROR: Job file not found: {job_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.gate == 1:
            approve_gate_1(job_path, args.approver)
        elif args.gate == 2:
            approve_gate_2(job_path, args.approver, reject=args.reject)
        elif args.gate == 3:
            approve_gate_3(job_path, args.approver)
        else:
            print(f"Gate {args.gate} approval not yet implemented", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
