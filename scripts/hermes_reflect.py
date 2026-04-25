#!/usr/bin/env python3
"""One-way reflection: append wiki/ changes to runtime/hermes/memory.md."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

def hermes_reflect(wiki_dir: Path, hermes_path: Path) -> None:
    """Scan wiki/ for new/modified files and append summary to Hermes memory."""
    hermes_path.parent.mkdir(parents=True, exist_ok=True)
    
    entries = []
    if wiki_dir.exists():
        for f in sorted(wiki_dir.iterdir()):
            if f.is_file():
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                entries.append(f"- {f.name} (updated {mtime.isoformat()})")
    
    if not entries:
        print("No wiki changes to reflect.")
        return
    
    summary = f"\n## Reflection at {datetime.now(timezone.utc).isoformat()}\n"
    summary += "\n".join(entries)
    summary += "\n"
    
    with open(hermes_path, "a", encoding="utf-8") as f:
        f.write(summary)
    
    print(f"Hermes memory updated: {len(entries)} entries")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-dir", default="wiki", help="Wiki directory")
    parser.add_argument("--hermes", default="runtime/hermes/memory.md", help="Hermes memory file")
    args = parser.parse_args()
    
    repo_root = Path(__file__).resolve().parents[1]
    wiki_path = repo_root / args.wiki_dir
    hermes_path = repo_root / args.hermes
    
    hermes_reflect(wiki_path, hermes_path)
