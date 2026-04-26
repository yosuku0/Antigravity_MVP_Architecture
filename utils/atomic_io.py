"""Atomic file I/O — per job_lifecycle_spec.md §2.1"""

import os
import shutil
import tempfile
from pathlib import Path
import yaml


def atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically using temp file + fsync + move."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode='w', delete=False, dir=path.parent, suffix='.tmp', encoding='utf-8'
    )
    try:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        shutil.move(tmp.name, path)
    except Exception:
        tmp.close()
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise


def atomic_append(path: Path, content: str) -> None:
    """Append content to file atomically using O_APPEND + fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if not content.endswith("\n"):
        content += "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())


def read_frontmatter(path: Path) -> tuple[dict, str]:
    """Read YAML frontmatter and body from a file."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) >= 3:
        try:
            fm = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            fm = {}
        body = parts[2]
        return fm, body
    return {}, text


def write_frontmatter(path: Path, fm: dict, body: str) -> None:
    """Write YAML frontmatter and body to a file atomically."""
    # default_flow_style=False ensures block style
    yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    if body.startswith('\n'):
        content = f"---\n{yaml_str}---{body}"
    else:
        content = f"---\n{yaml_str}---\n{body}"
    atomic_write(path, content)
