#!/usr/bin/env python3
"""Build a reproducible merged repair-training corpus for the TLA prover lane."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.rlvr_canary.repair_dataset import (
    DEFAULT_BENCHMARK_REPAIR_PAIRS,
    DEFAULT_REPAIR_PAIRS,
    resolve_repair_pair_paths,
)

DEFAULT_LONG_RALPH_REPAIR_PAIRS = "data/processed/ralph_repair_pairs_long_latest.jsonl"
DEFAULT_SYNTHETIC_REPAIR_PAIRS = "data/processed/tla_prover_synthetic_repair_pairs_v1.jsonl"
DEFAULT_FULL_DATASET_VALIDATED_REPAIR_PAIRS = "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "tla_prover_repair_train_v1.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _difficulty_bucket(before_score: float) -> str:
    if before_score < 0.10:
        return "easy"
    if before_score < 0.40:
        return "medium"
    return "hard"


def _is_benchmark_source(source_key: str) -> bool:
    return source_key.endswith("benchmark_repair_pairs_fc128best.jsonl")


def build_corpus(
    *,
    repair_pair_files: list[str | Path],
    repo: Path = REPO,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = resolve_repair_pair_paths(repair_pair_files)
    rows: list[dict[str, Any]] = []
    seen_repair_ids: set[str] = set()
    duplicate_repair_ids: list[str] = []
    missing_sources: list[str] = []
    source_rows: dict[str, int] = {}
    kept_rows_by_source: dict[str, int] = {}
    difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}

    for path in paths:
        source_key = str(path.relative_to(repo)) if path.is_relative_to(repo) else str(path)
        if not path.exists():
            missing_sources.append(source_key)
            continue
        source_payload = _read_jsonl(path)
        source_rows[source_key] = len(source_payload)
        kept_rows_by_source[source_key] = 0
        for row in source_payload:
            repair_id = str(row.get("repair_id", "")).strip()
            if not repair_id:
                continue
            if repair_id in seen_repair_ids:
                duplicate_repair_ids.append(repair_id)
                continue
            seen_repair_ids.add(repair_id)
            enriched = dict(row)
            enriched["source_file"] = source_key
            rows.append(enriched)
            kept_rows_by_source[source_key] += 1
            difficulty_counts[_difficulty_bucket(float(row.get("before_score", 0.0)))] += 1

    rows.sort(key=lambda item: (float(item.get("before_score", 0.0)), str(item.get("repair_id", ""))))
    benchmark_only = bool(rows) and all(_is_benchmark_source(source_key) for source_key in kept_rows_by_source)
    only_easy_rows = bool(rows) and difficulty_counts["easy"] == len(rows)
    non_benchmark_sources = [
        source_key for source_key, kept_rows in kept_rows_by_source.items()
        if kept_rows > 0 and not _is_benchmark_source(source_key)
    ]
    warnings: list[str] = []
    if any("ralph_repair_pairs" in source for source in missing_sources) and not non_benchmark_sources:
        warnings.append("missing_ralph_sources")
    if len(kept_rows_by_source) == 1 and rows:
        warnings.append("single_source_repair_corpus")
    if benchmark_only:
        warnings.append("benchmark_only_repair_corpus")
    if only_easy_rows:
        warnings.append("easy_only_repair_corpus")
    summary = {
        "schema": "chattla_tla_prover_repair_train_summary_v1",
        "rows": len(rows),
        "source_rows": source_rows,
        "kept_rows_by_source": kept_rows_by_source,
        "missing_sources": missing_sources,
        "duplicate_repair_ids": sorted(set(duplicate_repair_ids)),
        "difficulty_counts": difficulty_counts,
        "source_defaults": {
            "ralph_repair_pairs": DEFAULT_REPAIR_PAIRS,
            "ralph_repair_pairs_long_latest": DEFAULT_LONG_RALPH_REPAIR_PAIRS,
            "synthetic_repair_pairs": DEFAULT_SYNTHETIC_REPAIR_PAIRS,
            "full_dataset_validated_repair_pairs": DEFAULT_FULL_DATASET_VALIDATED_REPAIR_PAIRS,
            "benchmark_repair_pairs_fc128best": DEFAULT_BENCHMARK_REPAIR_PAIRS,
        },
        "health": {
            "ok": not warnings,
            "warnings": warnings,
            "benchmark_only": benchmark_only,
            "only_easy_rows": only_easy_rows,
        },
    }
    return rows, summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repair-pair-file",
        action="append",
        default=None,
        help=(
            "Repair-pair JSONL to include. Repeat to mix sources. "
            f"Defaults to `{DEFAULT_REPAIR_PAIRS}`, `{DEFAULT_LONG_RALPH_REPAIR_PAIRS}`, "
            f"`{DEFAULT_SYNTHETIC_REPAIR_PAIRS}`, "
            f"`{DEFAULT_FULL_DATASET_VALIDATED_REPAIR_PAIRS}`, "
            f"and `{DEFAULT_BENCHMARK_REPAIR_PAIRS}`."
        ),
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    repair_pair_files = list(
        args.repair_pair_file
        or [
            DEFAULT_REPAIR_PAIRS,
            DEFAULT_LONG_RALPH_REPAIR_PAIRS,
            DEFAULT_SYNTHETIC_REPAIR_PAIRS,
            DEFAULT_FULL_DATASET_VALIDATED_REPAIR_PAIRS,
            DEFAULT_BENCHMARK_REPAIR_PAIRS,
        ]
    )
    rows, summary = build_corpus(repair_pair_files=repair_pair_files)
    _write_jsonl(args.out, rows)
    summary_path = args.out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "summary": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
