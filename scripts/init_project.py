#!/usr/bin/env python3
"""
init_project.py — L0 workspace scaffolding

Creates a new project with:
  - domains/ structure
  - work/ directories
  - .agent_template/ with constitution
"""

import argparse
import shutil
from pathlib import Path

PROJECT_TEMPLATE = {
    "domains/game/raw": None,
    "domains/game/wiki": None,
    "domains/market/raw": None,
    "domains/market/wiki": None,
    "domains/personal/raw": None,
    "domains/personal/wiki": None,
    "work/jobs": None,
    "work/staged": None,
    "work/locks": None,
    "work/blackboard": None,
    "work/wiki": None,
    ".agent_template": None,
}

DOMAIN_DEFAULTS = {
    "domains/game/.domain": "name: game\ndescription: Game development knowledge\nallowed_squads:\n  - coding_squad\n  - research_squad\n  - review_squad\n",
    "domains/market/.domain": "name: market\ndescription: Market analysis\nallowed_squads:\n  - research_squad\n  - review_squad\n  - coding_squad\n",
    "domains/personal/.domain": "name: personal\ndescription: Personal knowledge\nallowed_squads:\n  - review_squad\n  - research_squad\n  - coding_squad\n",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize project workspace")
    parser.add_argument("name", help="Project name")
    parser.add_argument("--root", default=".", help="Parent directory")
    args = parser.parse_args()

    root = Path(args.root) / args.name
    if root.exists():
        print(f"[ERROR] Directory exists: {root}")
        return 1

    root.mkdir(parents=True)

    # Create directories
    for dir_name in PROJECT_TEMPLATE:
        (root / dir_name).mkdir(parents=True, exist_ok=True)

    # Create .domain files
    for file_name, content in DOMAIN_DEFAULTS.items():
        (root / file_name).write_text(content, encoding="utf-8")

    # Create global constitution
    constitution = root / ".agent_template" / "constitution.md"
    constitution.write_text(
        f"# {args.name} — Global Constitution\n\n"
        "## Principles\n- Safety first\n- Verify before execute\n- Audit everything\n\n"
        "## Domains\n- game: Game development\n- market: Market analysis\n- personal: Personal knowledge\n",
        encoding="utf-8",
    )

    print(f"[OK] Created project: {root}")
    print(f"       Domains: game, market, personal")
    print(f"       Work dirs: jobs, staged, locks, blackboard, wiki")
    return 0


if __name__ == "__main__":
    exit(main())
