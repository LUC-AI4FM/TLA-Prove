#!/usr/bin/env python3
"""Launch local TLA prover training with named corpus lanes."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.training.prover_corpus_selection import resolve_local_prover_train_selection

TRAIN_ENTRYPOINT = ["python3", "-m", "src.training.train", "--prover"]


def _safe_label(value: str | None) -> str:
    if not value:
        return "custom"
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower() or "custom"


def _default_output_dir(repo: Path, alias: str | None, *, requested_corpus: str | None) -> Path:
    if alias == "default" or (alias is None and not requested_corpus):
        return repo / "outputs" / "checkpoints_prover"
    return repo / "outputs" / f"checkpoints_prover_{_safe_label(alias or requested_corpus)}"


def _default_experiment_name(alias: str | None, *, requested_corpus: str | None) -> str:
    if alias == "default" or (alias is None and not requested_corpus):
        return "ChatTLA-Prover-gpt-oss-20b"
    return f"ChatTLA-Prover-gpt-oss-20b-{_safe_label(alias or requested_corpus)}"


def build_run_plan(
    *,
    repo: Path,
    requested_corpus: str | None,
    output_dir: str | None,
    experiment_name: str | None,
    extra_args: list[str],
) -> dict[str, Any]:
    selection = resolve_local_prover_train_selection(repo, requested=requested_corpus)
    metadata = dict(selection["metadata"])
    alias = metadata.get("alias")
    resolved_train_file = metadata.get("resolved_train_file")
    train_path = Path(selection["train_path"])
    final_output_dir = Path(output_dir) if output_dir else _default_output_dir(
        repo,
        alias,
        requested_corpus=requested_corpus,
    )
    final_experiment_name = experiment_name or _default_experiment_name(
        alias,
        requested_corpus=requested_corpus,
    )

    command = list(TRAIN_ENTRYPOINT)
    if resolved_train_file and alias:
        command.extend(["--sft-corpus", alias])
    else:
        command.extend(["--train-file", str(train_path)])
    command.extend(["--output-dir", str(final_output_dir)])
    command.extend(["--experiment-name", final_experiment_name])
    command.extend(extra_args)

    return {
        "schema": "chattla_tla_prover_local_train_plan_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "requested_corpus": requested_corpus,
        "resolved_corpus": metadata,
        "train_path": str(train_path),
        "output_dir": str(final_output_dir),
        "experiment_name": final_experiment_name,
        "command": command,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sft-corpus",
        default=os.environ.get("CHATTLA_TLA_PROVER_TRAIN_FILE"),
        help="default | expanded | full-public | shape-ready | shape-ready-not-sany | PATH",
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--experiment-name", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    extra_args = list(args.extra_args)
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    plan = build_run_plan(
        repo=REPO,
        requested_corpus=args.sft_corpus,
        output_dir=args.output_dir,
        experiment_name=args.experiment_name,
        extra_args=extra_args,
    )
    if args.dry_run:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    print(json.dumps(plan, indent=2, sort_keys=True))
    completed = subprocess.run(plan["command"], cwd=REPO)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
