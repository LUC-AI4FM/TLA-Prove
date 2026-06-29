"""Shared path helpers for TLA prover corpus selection."""
from __future__ import annotations

from pathlib import Path

DEFAULT_TRAINLIKE_PROBE_SOURCE = "data/processed/prover_train.jsonl"
DEFAULT_PROBE_FALLBACK = "data/processed/prover_eval.jsonl"
DEFAULT_LOCAL_SFT_TRAIN = "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl"
DEFAULT_PUBLIC_SFT_TRAIN = (
    "outputs/hf_publish/chattla-tla-prover-corpora-v1/data/train/chattla_tla_prover_sft_v1.jsonl"
)


def _exists(repo: Path, rel_path: str) -> bool:
    return (repo / rel_path).exists()


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
    candidates = [requested] if requested else [local_default, public_default]
    checked = [candidate for candidate in candidates if candidate]
    for candidate in checked:
        if _exists(repo, candidate):
            return candidate, checked
    return None, checked
