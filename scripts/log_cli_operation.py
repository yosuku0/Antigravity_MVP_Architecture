#!/usr/bin/env python3
"""Append one validated entry to logs/cli_operations.jsonl."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.cli_operations import build_cli_operation, log_cli_operation


def main() -> int:
    parser = argparse.ArgumentParser(description="Log a CLI operation")
    parser.add_argument("--cli", required=True, help="CLI or wrapper name")
    parser.add_argument("--action", required=True, help="read/write/edit/delete/status_update/etc")
    parser.add_argument("--target-path", required=True, help="Target path, preferably workspace-relative")
    parser.add_argument("--outcome", required=True, choices=["success", "failed", "skipped"])
    parser.add_argument("--actor", default=None)
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--detail", default="")
    parser.add_argument("--log-path", default="logs/cli_operations.jsonl")
    args = parser.parse_args()

    operation = build_cli_operation(
        cli=args.cli,
        action=args.action,
        target_path=args.target_path,
        outcome=args.outcome,
        actor=args.actor,
        job_id=args.job_id,
        detail=args.detail,
    )
    try:
        log_cli_operation(operation, Path(args.log_path))
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1
    print(f"Logged {args.action} by {args.cli} -> {args.target_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
