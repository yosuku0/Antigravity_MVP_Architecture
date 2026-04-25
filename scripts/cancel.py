#!/usr/bin/env python3
"""Cancel a job from any non-terminal state."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.atomic_io import atomic_write

def cancel_job(job_path: Path) -> None:
    """Cancel a job: remove lock, purge staged artifacts, set status to cancelled."""
    text = job_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("No frontmatter found")
    _, rest = text.split("---", 1)
    yaml_part, body = rest.split("---", 1)
    frontmatter = yaml.safe_load(yaml_part) or {}
    
    status = frontmatter.get("status")
    if status in {"promoted", "failed", "cancelled"}:
        print(f"Job is already terminal: {status}")
        return
    
    job_id = frontmatter.get("job_id", job_path.stem)
    repo_root = Path(__file__).resolve().parents[1]
    
    # Remove lock if exists
    lock_path = repo_root / "work" / "locks" / f"{job_id}.lock"
    if lock_path.exists():
        lock_path.unlink()
        print(f"Lock removed for {job_id}")
    
    # Purge staged artifacts if applicable
    staging_dir = repo_root / "work" / "artifacts" / "staging" / job_id
    if staging_dir.exists():
        import shutil
        shutil.rmtree(staging_dir)
        print(f"Staging purged for {job_id}")
    
    # Update status
    frontmatter["status"] = "cancelled"
    frontmatter["cancelled_at"] = datetime.now(timezone.utc).isoformat()
    yaml_text = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
    content = f"---\n{yaml_text}---\n\n{body.strip()}\n"
    atomic_write(job_path, content)
    print(f"Cancelled: {job_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, help="Path to JOB file")
    args = parser.parse_args()
    
    job_path = Path(args.job)
    if not job_path.exists():
        print(f"ERROR: Job not found: {job_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        cancel_job(job_path)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
