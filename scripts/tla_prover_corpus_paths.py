"""Shared path helpers for TLA prover corpus selection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_TRAINLIKE_PROBE_SOURCE = "data/processed/prover_train.jsonl"
DEFAULT_PROBE_FALLBACK = "data/processed/prover_eval.jsonl"
DEFAULT_LOCAL_SFT_TRAIN = "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl"
DEFAULT_PUBLIC_SFT_TRAIN = (
    "outputs/hf_publish/chattla-tla-prover-corpora-v1/data/train/chattla_tla_prover_sft_v1.jsonl"
)
EXPANDED_LOCAL_SFT_TRAIN = "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl"
FULL_PUBLIC_LOCAL_SFT_TRAIN = "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl"
SHAPE_READY_LOCAL_SFT_TRAIN = "data/processed/ai4fm_public_seed_prover_shape_ready_v1.jsonl"
SHAPE_READY_NOT_SANY_LOCAL_SFT_TRAIN = (
    "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.jsonl"
)
DEFAULT_LOCAL_SFT_SUMMARY = "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json"
DEFAULT_PUBLIC_SFT_SUMMARY = (
    "outputs/hf_publish/chattla-tla-prover-corpora-v1/metadata/chattla_tla_prover_sft_v1.summary.json"
)
EXPANDED_LOCAL_SFT_SUMMARY = (
    "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json"
)
FULL_PUBLIC_LOCAL_SFT_SUMMARY = (
    "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json"
)
SHAPE_READY_LOCAL_SFT_SUMMARY = "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json"
SHAPE_READY_NOT_SANY_LOCAL_SFT_SUMMARY = (
    "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json"
)
DEFAULT_CORPUS_EXPERIMENT_MATRIX = "outputs/manifests/tla_prover_corpus_experiment_matrix.json"

NAMED_SFT_CORPORA = {
    "default": None,
    "expanded": EXPANDED_LOCAL_SFT_TRAIN,
    "full-public": FULL_PUBLIC_LOCAL_SFT_TRAIN,
    "shape-ready": SHAPE_READY_LOCAL_SFT_TRAIN,
    "shape-ready-not-sany": SHAPE_READY_NOT_SANY_LOCAL_SFT_TRAIN,
}

SFT_SUMMARY_BY_TRAIN_FILE = {
    DEFAULT_LOCAL_SFT_TRAIN: DEFAULT_LOCAL_SFT_SUMMARY,
    DEFAULT_PUBLIC_SFT_TRAIN: DEFAULT_PUBLIC_SFT_SUMMARY,
    EXPANDED_LOCAL_SFT_TRAIN: EXPANDED_LOCAL_SFT_SUMMARY,
    FULL_PUBLIC_LOCAL_SFT_TRAIN: FULL_PUBLIC_LOCAL_SFT_SUMMARY,
    SHAPE_READY_LOCAL_SFT_TRAIN: SHAPE_READY_LOCAL_SFT_SUMMARY,
    SHAPE_READY_NOT_SANY_LOCAL_SFT_TRAIN: SHAPE_READY_NOT_SANY_LOCAL_SFT_SUMMARY,
}


def _exists(repo: Path, rel_path: str) -> bool:
    return (repo / rel_path).exists()


def resolve_named_sft_corpus(requested: str | None) -> str | None:
    if requested is None:
        return None
    normalized = requested.strip()
    if not normalized:
        return None
    return NAMED_SFT_CORPORA.get(normalized, normalized)


def resolve_probe_corpus_file(
    repo: Path,
    *,
    preferred: str = DEFAULT_TRAINLIKE_PROBE_SOURCE,
    fallback: str = DEFAULT_PROBE_FALLBACK,
) -> tuple[str, bool]:
    if _exists(repo, preferred):
        return preferred, False
    return fallback, True


def resolve_remote_sft_train_file(
    repo: Path,
    *,
    requested: str | None = None,
    local_default: str = DEFAULT_LOCAL_SFT_TRAIN,
    public_default: str = DEFAULT_PUBLIC_SFT_TRAIN,
) -> tuple[str | None, list[str]]:
    requested_path = resolve_named_sft_corpus(requested)
    candidates = [requested_path] if requested_path else [local_default, public_default]
    checked = [candidate for candidate in candidates if candidate]
    for candidate in checked:
        if _exists(repo, candidate):
            return candidate, checked
    return None, checked


def summary_path_for_sft_train_file(train_file: str | None) -> str | None:
    if train_file is None:
        return None
    return SFT_SUMMARY_BY_TRAIN_FILE.get(train_file)


def infer_named_sft_alias(train_file: str | None) -> str | None:
    if train_file is None:
        return None
    if train_file in {DEFAULT_LOCAL_SFT_TRAIN, DEFAULT_PUBLIC_SFT_TRAIN}:
        return "default"
    for alias, rel_path in NAMED_SFT_CORPORA.items():
        if rel_path and rel_path == train_file:
            return alias
    return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows_from_summary(summary: dict[str, Any]) -> int | None:
    for key in ("total_rows", "kept_rows", "rows"):
        value = summary.get(key)
        if value is not None:
            return int(value)
    return None


def resolve_remote_sft_corpus_metadata(
    repo: Path,
    *,
    requested: str | None = None,
    local_default: str = DEFAULT_LOCAL_SFT_TRAIN,
    public_default: str = DEFAULT_PUBLIC_SFT_TRAIN,
    experiment_matrix: str = DEFAULT_CORPUS_EXPERIMENT_MATRIX,
) -> dict[str, Any]:
    requested_path = resolve_named_sft_corpus(requested)
    resolved, checked = resolve_remote_sft_train_file(
        repo,
        requested=requested,
        local_default=local_default,
        public_default=public_default,
    )
    alias = infer_named_sft_alias(resolved or requested_path)
    summary_path = summary_path_for_sft_train_file(resolved or requested_path)
    rows = None
    default_publish_lane = None
    intended_role = None
    trainable = None
    matrix_rel = experiment_matrix
    matrix_path = repo / experiment_matrix
    matrix_lane_found = False

    if matrix_path.exists():
        try:
            matrix = _read_json(matrix_path)
        except json.JSONDecodeError:
            matrix = {}
        lanes = matrix.get("lanes", {})
        if alias and alias in lanes:
            lane = lanes[alias]
            rows = lane.get("rows")
            default_publish_lane = lane.get("default_publish_lane")
            intended_role = lane.get("intended_role")
            trainable = lane.get("trainable")
            matrix_lane_found = True

    if rows is None and summary_path and _exists(repo, summary_path):
        try:
            rows = _rows_from_summary(_read_json(repo / summary_path))
        except json.JSONDecodeError:
            rows = None

    return {
        "requested": requested,
        "requested_path": requested_path,
        "checked_paths": checked,
        "resolved_train_file": resolved,
        "alias": alias,
        "summary_path": summary_path,
        "rows": rows,
        "default_publish_lane": default_publish_lane,
        "intended_role": intended_role,
        "trainable": trainable,
        "experiment_matrix_path": matrix_rel,
        "experiment_matrix_present": matrix_path.exists(),
        "experiment_matrix_lane_found": matrix_lane_found,
    }


def _build_cli_report(repo: Path, requested: str | None) -> dict[str, object]:
    resolved = resolve_named_sft_corpus(requested)
    return {
        "requested": requested,
        "resolved": resolved,
        "named_corpora": NAMED_SFT_CORPORA,
        "remote_sft_metadata": resolve_remote_sft_corpus_metadata(repo, requested=requested),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--resolve-request", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = _build_cli_report(args.repo, args.resolve_request)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["resolved"] or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
