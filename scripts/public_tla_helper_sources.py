#!/usr/bin/env python3
"""Shared defaults for public helper-module corpora used in seed repair analysis."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_FORMALLLM_HELPER_SOURCE = REPO / "data" / "processed" / "formalllm_public_tla_modules_v1.jsonl"
DEFAULT_TLAPM_HELPER_SOURCE = REPO / "data" / "processed" / "tlapm_public_tla_modules_v1.jsonl"


def default_existing_helper_sources() -> list[Path]:
    paths: list[Path] = []
    for path in [DEFAULT_FORMALLLM_HELPER_SOURCE, DEFAULT_TLAPM_HELPER_SOURCE]:
        if path.exists():
            paths.append(path)
    return paths
