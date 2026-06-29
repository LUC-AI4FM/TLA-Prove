"""Shared path helpers for TLA prover corpus selection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

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

NAMED_SFT_CORPORA = {
    "default": None,
    "expanded": EXPANDED_LOCAL_SFT_TRAIN,
    "full-public": FULL_PUBLIC_LOCAL_SFT_TRAIN,
    "shape-ready": SHAPE_READY_LOCAL_SFT_TRAIN,
    "shape-ready-not-sany": SHAPE_READY_NOT_SANY_LOCAL_SFT_TRAIN,
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


def _build_cli_report(requested: str | None) -> dict[str, object]:
    resolved = resolve_named_sft_corpus(requested)
    return {
        "requested": requested,
        "resolved": resolved,
        "named_corpora": NAMED_SFT_CORPORA,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolve-request", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = _build_cli_report(args.resolve_request)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["resolved"] or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
