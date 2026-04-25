"""Atomic file I/O — per job_lifecycle_spec.md §2.1"""

import os
import shutil
import tempfile
from pathlib import Path


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


def atomic_append(path: Path, line: str) -> None:
    """Append a single line to a JSONL file atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode='a+', delete=False, dir=path.parent, suffix='.tmp', encoding='utf-8'
    )
    try:
        # If file exists, copy existing content
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                tmp.write(f.read())
        tmp.write(line.rstrip('\n') + '\n')
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        shutil.move(tmp.name, path)
    except Exception:
        tmp.close()
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise
