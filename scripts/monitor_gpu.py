#!/usr/bin/env python3
"""Collect nvidia-smi metrics into logs/gpu_metrics.csv.

The script degrades cleanly when NVIDIA tooling is unavailable, which keeps the
Windows-first workflow usable on machines without Docker GPU setup.
"""

import argparse
import csv
import shutil
import subprocess
import sys
import time
from pathlib import Path


CSV_FIELDS = [
    "ts",
    "index",
    "name",
    "utilization_gpu_percent",
    "memory_used_mib",
    "memory_total_mib",
    "temperature_gpu_c",
    "power_draw_w",
]


def parse_nvidia_smi_csv(output: str, timestamp: str) -> list[dict]:
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 7:
            continue
        rows.append({
            "ts": timestamp,
            "index": parts[0],
            "name": parts[1],
            "utilization_gpu_percent": parts[2],
            "memory_used_mib": parts[3],
            "memory_total_mib": parts[4],
            "temperature_gpu_c": parts[5],
            "power_draw_w": parts[6],
        })
    return rows


def collect_once() -> list[dict]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    query = (
        "index,name,utilization.gpu,memory.used,memory.total,"
        "temperature.gpu,power.draw"
    )
    proc = subprocess.run(
        [
            exe,
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return parse_nvidia_smi_csv(proc.stdout, timestamp)


def append_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if needs_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor NVIDIA GPU metrics")
    parser.add_argument("--output", default="logs/gpu_metrics.csv")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--count", type=int, default=1, help="Number of samples; 0 means forever")
    args = parser.parse_args()

    samples = 0
    while args.count == 0 or samples < args.count:
        rows = collect_once()
        if rows:
            append_rows(Path(args.output), rows)
            print(f"wrote {len(rows)} GPU metric row(s)")
        else:
            print("nvidia-smi unavailable or returned no rows; skipped")
        samples += 1
        if args.count != 0 and samples >= args.count:
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
