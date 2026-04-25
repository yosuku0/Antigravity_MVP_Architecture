#!/usr/bin/env python3
"""Wiki promotion script — writes to wiki/ only in PROMOTED state."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
import yaml
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.atomic_io import atomic_write

def stage_promotion(job_path: Path, repo_root: Path = None) -> Path:
    """Stage raw/ content for promotion. Returns staging directory."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]
    # Read job frontmatter
    text = job_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("No frontmatter found")
    _, rest = text.split("---", 1)
    yaml_part, body = rest.split("---", 1)
    frontmatter = yaml.safe_load(yaml_part) or {}
    
    # Validate prerequisites
    if frontmatter.get("audit_result") != "pass":
        print("ERROR: audit_result != pass. Fix audit issues before promotion.", file=sys.stderr)
        sys.exit(1)
    
    if not frontmatter.get("approved_gate_2_by"):
        print("ERROR: Gate 2 approval required.", file=sys.stderr)
        sys.exit(1)
    
    # Stage content
    job_id = frontmatter.get("job_id", job_path.stem)
    staging_dir = repo_root / "work" / "artifacts" / "staging" / job_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy artifacts from memory/working/{job_id} to staging
    working_dir = repo_root / "memory" / "working" / job_id
    if working_dir.exists():
        for f in working_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, staging_dir / f.name)
    else:
        print(f"WARN: Working dir not found: {working_dir}")
    
    # Update status
    frontmatter["status"] = "promotion_pending"
    yaml_text = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
    content = f"---\n{yaml_text}---\n\n{body.strip()}\n"
    atomic_write(job_path, content)
    
    print(f"Staged for promotion: {job_id} → {staging_dir}")
    return staging_dir

def promote_to_wiki(job_path: Path, approver: str = "higurashi", repo_root: Path = None) -> None:
    """Promote staged content to wiki/ after Gate 3 approval."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]
    text = job_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("No frontmatter found")
    _, rest = text.split("---", 1)
    yaml_part, body = rest.split("---", 1)
    frontmatter = yaml.safe_load(yaml_part) or {}
    
    # Validate Gate 3
    status = frontmatter.get("status")
    if status != "promotion_pending" and status != "approved_gate_3":
        print(f"ERROR: Expected status 'promotion_pending' or 'approved_gate_3', got '{status}'", file=sys.stderr)
        sys.exit(1)
    
    if not frontmatter.get("approved_gate_3_by"):
        print("ERROR: Gate 3 approval required for wiki write.", file=sys.stderr)
        sys.exit(1)
    
    # Write to wiki/
    job_id = frontmatter.get("job_id", job_path.stem)
    staging_dir = repo_root / "work" / "artifacts" / "staging" / job_id
    wiki_dir = repo_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    
    if not staging_dir.exists():
        print(f"ERROR: Staging directory not found: {staging_dir}", file=sys.stderr)
        sys.exit(1)
        
    for f in staging_dir.iterdir():
        if f.is_file():
            dest = wiki_dir / f.name
            shutil.copy2(f, dest)
            print(f"Promoted: {f.name} → {dest}")
    
    # Update status to PROMOTED
    frontmatter["status"] = "promoted"
    frontmatter["promoted_at"] = datetime.now(timezone.utc).isoformat()
    yaml_text = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
    content = f"---\n{yaml_text}---\n\n{body.strip()}\n"
    atomic_write(job_path, content)
    
    # After wiki write, update Hermes memory
    import subprocess
    hermes_script = repo_root / "scripts" / "hermes_reflect.py"
    subprocess.run([sys.executable, str(hermes_script)], check=False)
    
    print(f"PROMOTED: {job_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, help="Path to JOB file")
    parser.add_argument("--stage", action="store_true", help="Stage content for promotion")
    parser.add_argument("--promote", action="store_true", help="Promote staged content to wiki")
    parser.add_argument("--approved-by", default="higurashi", help="Gate 3 approver")
    args = parser.parse_args()
    
    job_path = Path(args.job)
    if not job_path.exists():
        print(f"ERROR: Job not found: {job_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.stage:
            stage_promotion(job_path)
        elif args.promote:
            promote_to_wiki(job_path, args.approved_by)
        else:
            print("ERROR: Specify --stage or --promote", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
