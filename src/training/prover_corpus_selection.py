"""Lightweight helpers for selecting local prover training corpora."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.tla_prover_corpus_paths import (
    DEFAULT_LOCAL_SFT_TRAIN,
    resolve_named_sft_corpus,
    resolve_remote_sft_corpus_metadata,
)


def _path_from_request(repo: Path, requested: str | None) -> Path:
    resolved = resolve_named_sft_corpus(requested)
    if resolved is None:
        return repo / DEFAULT_LOCAL_SFT_TRAIN
    path = Path(resolved)
    return path if path.is_absolute() else repo / path


def resolve_local_prover_train_selection(
    repo: Path,
    *,
    requested: str | None,
) -> dict[str, Any]:
    train_path = _path_from_request(repo, requested)
    metadata = resolve_remote_sft_corpus_metadata(repo, requested=requested)
    return {
        "requested": requested,
        "train_path": train_path,
        "metadata": metadata,
    }
