#!/usr/bin/env python3
"""Knowledge ingestion script using liteparse."""
import argparse
import subprocess
import os
import sys
from pathlib import Path

def ingest_file(input_path: Path, output_dir: Path):
    """Parse a file using liteparse and save to wiki."""
    if not input_path.exists():
        print(f"Error: Input file {input_path} not found.")
        return False
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}.md"
    
    print(f"Ingesting {input_path} using liteparse...")
    
    # Call liteparse CLI via npx
    # Using lit parse <file> -o <output>
    # Note: lit is installed locally in node_modules
    try:
        # We use lit.cmd on Windows if npx lit doesn't work well
        cmd = ["npx.cmd", "lit", "parse", str(input_path), "-o", str(output_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Successfully ingested to {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during liteparse execution: {e.stderr}")
        # Fallback to simple read if it's already a text file
        if input_path.suffix in (".txt", ".md"):
            print("Fallback: Simple copy for text/md file.")
            output_path.write_text(input_path.read_text(encoding="utf-8"), encoding="utf-8")
            return True
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="File to ingest from work/raw/")
    parser.add_argument("--wiki", default="wiki", help="Target wiki directory")
    args = parser.parse_args()
    
    input_file = Path(args.file)
    wiki_dir = Path(args.wiki)
    
    ingest_file(input_file, wiki_dir)
