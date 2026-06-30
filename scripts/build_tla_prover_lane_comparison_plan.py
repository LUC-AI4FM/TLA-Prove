#!/usr/bin/env python3
"""Build a reproducible baseline-vs-candidate TLA prover lane comparison plan."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.tla_prover_corpus_paths import resolve_remote_sft_corpus_metadata
from scripts.train_tla_prover_local import build_run_plan as build_local_run_plan

DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_lane_comparison_plan.json"


def _safe_label(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower() or "comparison"


def _comparison_id(*, baseline: str, candidate: str, mode: str) -> str:
    return f"{_safe_label(baseline)}-vs-{_safe_label(candidate)}-{_safe_label(mode)}"


def _sanitize_value(value: Any, repo: Path) -> Any:
    if isinstance(value, dict):
        sanitized = {key: _sanitize_value(item, repo) for key, item in value.items()}
        if sanitized.get("repo") == str(repo):
            sanitized["repo"] = "."
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item, repo) for item in value]
    if isinstance(value, str) and value.startswith(str(repo)):
        try:
            return str(Path(value).resolve().relative_to(repo.resolve()))
        except ValueError:
            return value
    return value


def _local_lane_plan(
    *,
    repo: Path,
    requested_corpus: str,
    extra_args: list[str],
) -> dict[str, Any]:
    return _sanitize_value(
        build_local_run_plan(
            repo=repo,
            requested_corpus=requested_corpus,
            output_dir=None,
            experiment_name=None,
            extra_args=extra_args,
        ),
        repo=repo,
    )


def _remote_lane_plan(
    *,
    repo: Path,
    requested_corpus: str,
) -> dict[str, Any]:
    metadata = resolve_remote_sft_corpus_metadata(repo, requested=requested_corpus)
    corpus_arg = metadata.get("alias") or requested_corpus
    return {
        "requested_corpus": requested_corpus,
        "resolved_corpus": metadata,
        "remote_command": (
            "scripts/sync_sophia_and_submit_known18.sh "
            f"--sft-corpus {corpus_arg} --submit-sft-preflight"
        ),
    }


def _row_delta(baseline: dict[str, Any], candidate: dict[str, Any]) -> int | None:
    baseline_rows = baseline.get("resolved_corpus", {}).get("rows")
    candidate_rows = candidate.get("resolved_corpus", {}).get("rows")
    if baseline_rows is None or candidate_rows is None:
        return None
    return int(candidate_rows) - int(baseline_rows)


def build_plan(
    *,
    repo: Path,
    baseline: str,
    candidate: str,
    mode: str,
    extra_args: list[str],
) -> dict[str, Any]:
    if mode not in {"local", "remote"}:
        raise ValueError(f"mode must be 'local' or 'remote', got {mode!r}")
    if baseline == candidate:
        raise ValueError("baseline and candidate must differ")

    if mode == "local":
        baseline_plan = _local_lane_plan(repo=repo, requested_corpus=baseline, extra_args=extra_args)
        candidate_plan = _local_lane_plan(repo=repo, requested_corpus=candidate, extra_args=extra_args)
    else:
        baseline_plan = _remote_lane_plan(repo=repo, requested_corpus=baseline)
        candidate_plan = _remote_lane_plan(repo=repo, requested_corpus=candidate)

    payload = {
        "schema": "chattla_tla_prover_lane_comparison_plan_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "comparison_id": _comparison_id(baseline=baseline, candidate=candidate, mode=mode),
        "mode": mode,
        "baseline": baseline_plan,
        "candidate": candidate_plan,
        "row_delta": _row_delta(baseline_plan, candidate_plan),
        "follow_up": {
            "status_command": "python3 scripts/choose_tla_prover_next_experiment.py",
            "watch_command": "scripts/watch_tla_prover_remote_results.sh",
            "collect_command": "scripts/collect_tla_prover_remote_results.sh",
            "evaluate_command": "python3 scripts/evaluate_tla_prover_remote_results.py",
        },
    }
    return _sanitize_value(payload, repo)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--mode", choices=("local", "remote"), default="local")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("extra_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    extra_args = list(args.extra_args)
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    payload = build_plan(
        repo=args.repo,
        baseline=args.baseline,
        candidate=args.candidate,
        mode=args.mode,
        extra_args=extra_args,
    )
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
