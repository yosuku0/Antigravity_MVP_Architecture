#!/usr/bin/env python3
"""Scaffold a new project with .agent/ template."""
import argparse
from pathlib import Path
import shutil

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / ".agent_template"

def init_project(project_name: str, target_dir: Path = None):
    target = (target_dir or Path.cwd()) / project_name
    target.mkdir(parents=True, exist_ok=True)
    
    # Copy .agent template
    shutil.copytree(TEMPLATE_DIR / ".agent", target / ".agent", dirs_exist_ok=True)
    
    # Create control-plane
    (target / "control-plane" / "constitutions").mkdir(parents=True, exist_ok=True)
    global_md = Path(__file__).resolve().parents[1] / "control-plane" / "constitutions" / "global.md"
    if global_md.exists():
        shutil.copy2(global_md, target / "control-plane" / "constitutions" / "global.md")
    
    print(f"Project scaffolded: {target}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    parser.add_argument("--target", type=Path, default=None)
    args = parser.parse_args()
    init_project(args.project_name, args.target)
