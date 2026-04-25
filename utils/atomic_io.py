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


def atomic_append(path: Path, content: str) -> None:
    """Append content to file atomically using O_APPEND + fsync.

    This replaces the previous O(N^2) implementation that re-read
    the entire file on every append.

    NOTE: On Windows, file append atomicity is weaker than POSIX.
    Single-line JSONL appends are practically safe.
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Open in append mode, write, and fsync
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
