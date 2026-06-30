#!/usr/bin/env python3
"""Launch local TLA prover repair training with reproducible corpus selection."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.train_rl_repair import (
    DEFAULT_BENCHMARK_REPAIR_PAIRS,
    DEFAULT_MERGED_REPAIR_PAIRS,
    build_preflight_report,
    resolve_trajectory_files,
)
TRAIN_ENTRYPOINT = ["python3", "-m", "scripts.train_rl_repair"]


def _safe_label(value: str | None) -> str:
    if not value:
        return "custom"
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower() or "custom"


def _default_output_dir(repo: Path, resolved_trajectory_files: list[str]) -> Path:
    if resolved_trajectory_files == [DEFAULT_MERGED_REPAIR_PAIRS]:
        return repo / "outputs" / "checkpoints_rl_repair"

    primary = next(
        (
            path
            for path in resolved_trajectory_files
            if path != DEFAULT_BENCHMARK_REPAIR_PAIRS
        ),
        resolved_trajectory_files[0] if resolved_trajectory_files else None,
    )
    return repo / "outputs" / f"checkpoints_rl_repair_{_safe_label(primary)}"


def _build_args(
    *,
    trajectory_files: list[str] | None,
    include_benchmark_repair_pairs: bool,
) -> Namespace:
    return Namespace(
        trajectory_file=list(trajectory_files or []),
        include_benchmark_repair_pairs=include_benchmark_repair_pairs,
    )


def build_run_plan(
    *,
    repo: Path,
    trajectory_files: list[str] | None,
    include_benchmark_repair_pairs: bool,
    output_dir: str | None,
    extra_args: list[str],
    preflight_only: bool,
) -> dict[str, Any]:
    args = _build_args(
        trajectory_files=trajectory_files,
        include_benchmark_repair_pairs=include_benchmark_repair_pairs,
    )
    resolved_trajectory_files = resolve_trajectory_files(args, repo_root=repo)
    preflight_report = build_preflight_report(args, repo_root=repo)
    final_output_dir = Path(output_dir) if output_dir else _default_output_dir(repo, resolved_trajectory_files)

    command = list(TRAIN_ENTRYPOINT)
    for path in resolved_trajectory_files:
        command.extend(["--trajectory-file", path])
    command.extend(["--output-dir", str(final_output_dir)])
    if preflight_only:
        command.append("--preflight-only")
    command.extend(extra_args)

    return {
        "schema": "chattla_tla_prover_local_repair_plan_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "resolved_trajectory_files": resolved_trajectory_files,
        "using_merged_default": resolved_trajectory_files == [DEFAULT_MERGED_REPAIR_PAIRS],
        "include_benchmark_repair_pairs": include_benchmark_repair_pairs,
        "preflight_only": preflight_only,
        "preflight_report": preflight_report,
        "output_dir": str(final_output_dir),
        "command": command,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-file", action="append", default=None)
    parser.add_argument("--include-benchmark-repair-pairs", action="store_true")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    extra_args = list(args.extra_args)
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    plan = build_run_plan(
        repo=REPO,
        trajectory_files=args.trajectory_file,
        include_benchmark_repair_pairs=args.include_benchmark_repair_pairs,
        output_dir=args.output_dir,
        extra_args=extra_args,
        preflight_only=args.preflight,
    )
    print(json.dumps(plan, indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    completed = subprocess.run(plan["command"], cwd=REPO)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
