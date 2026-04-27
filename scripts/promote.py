#!/usr/bin/env python3
"""
promote.py — State-aware artifact staging and wiki promotion

Usage:
    python scripts/promote.py --job JOB-001 --mode stage
    python scripts/promote.py --job JOB-001 --mode execute

Flow:
  1. stage: Copy artifact to staging, record hash (Gate 2 -> Pending)
  2. execute: Verify hash, signatures, and promote to KnowledgeOS (Gate 3 -> Promoted)
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Allow importing from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.audit import audit_file
from domains.knowledge_os import KnowledgeOS, DomainError


# ── Configuration ─────────────────────────────────────────────────────

STAGING_DIR = Path("work/artifacts/staging")
ALLOWED_DOMAINS = {"game", "market", "personal"}

# ── Utilities ─────────────────────────────────────────────────────────

def compute_hash(path: Path) -> str:
    """Full SHA-256 hex digest of file contents for integrity verification."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def is_under_directory(path: Path, base_dir: Path) -> bool:
    """Security check to ensure path is within base_dir."""
    try:
        path.resolve().relative_to(base_dir.resolve())
        return True
    except (ValueError, RuntimeError):
        return False


def log_incident(incident_type: str, resource: str, detail: str) -> None:
    """Log an incident to daemon.jsonl."""
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "incident",
        "incident": incident_type,
        "resource": resource,
        "detail": detail,
    }
    from utils.atomic_io import atomic_append
    atomic_append(Path("work/daemon.jsonl"), json.dumps(entry, ensure_ascii=False) + "\n")


# ── Core Modes ───────────────────────────────────────────────────────

def stage_job(job_path: Path) -> bool:
    """Mode: stage (approved_gate_2 -> promotion_pending)"""
    from utils.atomic_io import read_frontmatter, write_frontmatter
    fm, body = read_frontmatter(job_path)
    job_id = fm.get("job_id", job_path.stem)

    # 1. Prerequisites
    status = fm.get("status")
    if status != "approved_gate_2":
        print(f"[ERROR] Stage DENIED: Current status is '{status}', expected 'approved_gate_2'")
        return False
    
    if fm.get("audit_result") != "pass":
        print(f"[ERROR] Stage DENIED: audit_result is '{fm.get('audit_result')}', must be 'pass'")
        return False

    artifact_path_str = fm.get("artifact_path")
    if not artifact_path_str:
        print("[ERROR] Stage failed: 'artifact_path' missing in JOB frontmatter")
        return False
    
    artifact_path = Path(artifact_path_str)
    if not artifact_path.exists():
        print(f"[ERROR] Stage failed: Artifact file not found: {artifact_path}")
        return False

    # 2. Process
    try:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        staged_path = STAGING_DIR / f"{job_id}.md"
        
        # Copy to staging (copy2 preserves metadata)
        import shutil
        shutil.copy2(artifact_path, staged_path)
        
        # Hash for integrity
        artifact_hash = compute_hash(staged_path)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Update FM
        fm["status"] = "promotion_pending"
        fm["staged_artifact_path"] = str(staged_path)
        fm["artifact_hash"] = artifact_hash
        fm["staged_at"] = now
        fm["stage_operator"] = "daemon"
        
        write_frontmatter(job_path, fm, body)
        print(f"[OK] Staged artifact to {staged_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Staging failed: {e}")
        return False


def execute_job(job_path: Path) -> bool:
    """Mode: execute (approved_gate_3 -> promoted)"""
    from utils.atomic_io import read_frontmatter, write_frontmatter
    fm, body = read_frontmatter(job_path)
    job_id = fm.get("job_id", job_path.stem)

    # 1. Prerequisites
    status = fm.get("status")
    if status != "approved_gate_3":
        print(f"[ERROR] Execute DENIED: Current status is '{status}', expected 'approved_gate_3'")
        return False
    
    if fm.get("audit_result") != "pass":
        print("[ERROR] Execute DENIED: audit_result is not 'pass'")
        return False

    # Mandatory HITL Proof
    if not fm.get("approved_gate_2_by") or not fm.get("approved_gate_3_by"):
        print("[ERROR] Execute failed: Missing Gate 2 or Gate 3 approver signatures")
        return False

    staged_path_str = fm.get("staged_artifact_path")
    expected_hash = fm.get("artifact_hash")
    if not staged_path_str or not expected_hash:
        print("[ERROR] Execute failed: Staging info (path or hash) missing")
        return False

    staged_path = Path(staged_path_str)
    
    # Path traversal check for staged_path (must be in staging dir)
    if not is_under_directory(staged_path, STAGING_DIR):
        print(f"[ERROR] Security: staged_artifact_path '{staged_path}' is outside staging directory")
        return False

    if not staged_path.exists():
        print(f"[ERROR] Execute failed: Staged artifact not found: {staged_path}")
        return False

    # Checksum verification (Detect tampering between Gate 2 and 3)
    current_hash = compute_hash(staged_path)
    if current_hash != expected_hash:
        print(f"[ERROR] Integrity: Hash mismatch! Expected {expected_hash}, got {current_hash}. Promotion BLOCKED.")
        log_incident("staged_artifact_tampered", str(staged_path), f"expected={expected_hash}, actual={current_hash}")
        return False

    # Topic / Domain resolution (No default domain allowed)
    domain = fm.get("domain")
    topic = fm.get("topic") or job_id
    
    # Validation
    if not domain or domain not in ALLOWED_DOMAINS:
        print(f"[ERROR] Invalid or missing domain: '{domain}'. Must be one of {ALLOWED_DOMAINS}")
        return False

    # Topic validation (no path traversal allowed in topic slug)
    if any(c in topic for c in ["..", "/", "\\"]):
        print(f"[ERROR] Security: Invalid topic name (path traversal detected): {topic}")
        return False

    # 2. Process
    try:
        content = staged_path.read_text(encoding="utf-8")
        kos = KnowledgeOS()
        wiki_path = kos.save(
            domain=domain,
            topic=topic,
            content=content,
            frontmatter={
                "job_id": job_id,
                "staged_hash": expected_hash,
                "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        
        # Update FM
        fm["status"] = "promoted"
        fm["promoted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        fm["promoted_hash"] = expected_hash
        fm["promoted_path"] = str(wiki_path)
        
        write_frontmatter(job_path, fm, body)
        print(f"[OK] Promoted to {wiki_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Execution failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote artifact to wiki (State-aware)")
    parser.add_argument("--job", required=True, help="Job ID or path to JOB file")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["stage", "execute"],
        help="Promotion mode: 'stage' (from Gate 2) or 'execute' (from Gate 3)",
    )
    
    args = parser.parse_args()

    job_path = Path(args.job)
    if not job_path.exists():
        job_path = Path("work/jobs") / f"{args.job}.md"
    
    if not job_path.exists():
        print(f"[ERROR] JOB file not found: {args.job}")
        return 1

    if args.mode == "stage":
        success = stage_job(job_path)
    elif args.mode == "execute":
        success = execute_job(job_path)
    else:
        success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
