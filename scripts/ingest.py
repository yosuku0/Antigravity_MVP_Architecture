#!/usr/bin/env python3
"""Knowledge ingestion script using liteparse."""
import argparse
import os
import sys
from pathlib import Path
from utils.atomic_io import atomic_write

def ingest_file(input_path: Path, output_dir: Path):
    """Parse a file using liteparse and save to wiki."""
    if not input_path.exists():
        print(f"Error: Input file {input_path} not found.")
        return False
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}.md"
    
    print(f"Ingesting {input_path} (Python-only mode)...")
    
    # subprocess 排除後の純粋 Python 実装
    try:
        content = input_path.read_text(encoding="utf-8")
        atomic_write(output_path, content)
        print(f"[OK] Ingested: {output_path}")
        return True
    except UnicodeDecodeError as e:
        print(f"[ERROR] Cannot decode {input_path}: {e}")
        return False
    except Exception as e:
        print(f"[WARN] Failed to ingest {input_path}: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="File to ingest from work/raw/")
    parser.add_argument("--wiki", default="wiki", help="Target wiki directory")
    args = parser.parse_args()
    
    input_file = Path(args.file)
    wiki_dir = Path(args.wiki)
    
    ingest_file(input_file, wiki_dir)
