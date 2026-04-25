"""Atomic file write utilities per job_lifecycle_spec.md §2.1."""
import os
import shutil
import tempfile
import yaml
from pathlib import Path

def atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically using temp file + rename."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        dir=path.parent,
        suffix=".tmp",
        encoding="utf-8",
    )
    try:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        shutil.move(tmp.name, path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass
        raise

def read_frontmatter(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text) from a JOB .md file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    _, rest = text.split("---", 1)
    yaml_part, body = rest.split("---", 1)
    frontmatter = yaml.safe_load(yaml_part) or {}
    return frontmatter, body.strip()

def write_frontmatter(path: Path, frontmatter: dict, body: str) -> None:
    """Write frontmatter + body atomically."""
    yaml_text = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
    content = f"---\n{yaml_text}---\n\n{body}\n"
    atomic_write(path, content)
