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
DEFAULT_FULL_DATASET_HARNESS_REPAIR_PAIRS = "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.jsonl"
DEFAULT_PROFILE = "default"
PROOF_REPAIR_PRIMARY_PROFILE = "proof_repair_primary"
VALID_PROFILES = (DEFAULT_PROFILE, PROOF_REPAIR_PRIMARY_PROFILE)


def default_out_for_profile(profile: str = DEFAULT_PROFILE, *, repo: Path = REPO) -> Path:
    if profile == DEFAULT_PROFILE:
        return repo / "data" / "processed" / "tla_prover_repair_train_v1.jsonl"
    if profile == PROOF_REPAIR_PRIMARY_PROFILE:
        return repo / "data" / "processed" / "tla_prover_repair_train_proof_repair_primary_v1.jsonl"
    raise ValueError(f"Unsupported repair corpus profile: {profile!r}")


DEFAULT_OUT = default_out_for_profile()


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


def _source_kind(source_key: str) -> str:
    if source_key.endswith("benchmark_repair_pairs_fc128best.jsonl"):
        return "benchmark_repair_pairs_fc128best"
    if source_key.endswith("tla_prover_synthetic_repair_pairs_v1.jsonl"):
        return "synthetic_repair_pairs"
    if source_key.endswith("tla_prover_full_dataset_validated_repair_pairs_v1.jsonl"):
        return "full_dataset_validated_repair_pairs"
    if source_key.endswith("tla_prover_full_dataset_harness_repair_pairs_v1.jsonl"):
        return "full_dataset_harness_repair_pairs"
    if source_key.endswith("ralph_repair_pairs_long_latest.jsonl"):
        return "ralph_repair_pairs_long_latest"
    if source_key.endswith("ralph_repair_pairs.jsonl"):
        return "ralph_repair_pairs"
    return "other"


def _profile_focus_bucket(profile: str) -> str | None:
    if profile == PROOF_REPAIR_PRIMARY_PROFILE:
        return "proof_repair"
    return None


def _row_matches_profile(*, row: dict[str, Any], source_key: str, profile: str) -> bool:
    if profile == DEFAULT_PROFILE:
        return True
    if profile == PROOF_REPAIR_PRIMARY_PROFILE:
        if _is_benchmark_source(source_key):
            return True
        return str(row.get("repair_bucket") or "").strip() == "proof_repair"
    raise ValueError(f"Unsupported repair corpus profile: {profile!r}")


def build_corpus(
    *,
    repair_pair_files: list[str | Path],
    profile: str = DEFAULT_PROFILE,
    repo: Path = REPO,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if profile not in VALID_PROFILES:
        raise ValueError(f"profile must be one of {VALID_PROFILES}, got {profile!r}")
    paths = resolve_repair_pair_paths(repair_pair_files)
    rows: list[dict[str, Any]] = []
    seen_repair_ids: set[str] = set()
    duplicate_repair_ids: list[str] = []
    missing_sources: list[str] = []
    source_rows: dict[str, int] = {}
    kept_rows_by_source: dict[str, int] = {}
    profile_excluded_rows: dict[str, int] = {}
    difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
    rows_by_repair_bucket: dict[str, int] = {}
    rows_without_repair_bucket = 0
    rows_by_source_kind: dict[str, int] = {}

    for path in paths:
        source_key = str(path.relative_to(repo)) if path.is_relative_to(repo) else str(path)
        if not path.exists():
            missing_sources.append(source_key)
            continue
        source_payload = _read_jsonl(path)
        source_rows[source_key] = len(source_payload)
        kept_rows_by_source[source_key] = 0
        profile_excluded_rows[source_key] = 0
        for row in source_payload:
            repair_id = str(row.get("repair_id", "")).strip()
            if not repair_id:
                continue
            if not _row_matches_profile(row=row, source_key=source_key, profile=profile):
                profile_excluded_rows[source_key] += 1
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
            repair_bucket = str(row.get("repair_bucket") or "").strip()
            if repair_bucket:
                rows_by_repair_bucket[repair_bucket] = rows_by_repair_bucket.get(repair_bucket, 0) + 1
            else:
                rows_without_repair_bucket += 1
            source_kind = _source_kind(source_key)
            rows_by_source_kind[source_kind] = rows_by_source_kind.get(source_kind, 0) + 1

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
        "profile": profile,
        "focus_bucket": _profile_focus_bucket(profile),
        "rows": len(rows),
        "source_rows": source_rows,
        "kept_rows_by_source": kept_rows_by_source,
        "profile_excluded_rows": {key: value for key, value in profile_excluded_rows.items() if value > 0},
        "missing_sources": missing_sources,
        "duplicate_repair_ids": sorted(set(duplicate_repair_ids)),
        "difficulty_counts": difficulty_counts,
        "rows_by_repair_bucket": dict(sorted(rows_by_repair_bucket.items())),
        "rows_without_repair_bucket": rows_without_repair_bucket,
        "rows_by_source_kind": dict(sorted(rows_by_source_kind.items())),
        "source_defaults": {
            "ralph_repair_pairs": DEFAULT_REPAIR_PAIRS,
            "ralph_repair_pairs_long_latest": DEFAULT_LONG_RALPH_REPAIR_PAIRS,
            "synthetic_repair_pairs": DEFAULT_SYNTHETIC_REPAIR_PAIRS,
            "full_dataset_validated_repair_pairs": DEFAULT_FULL_DATASET_VALIDATED_REPAIR_PAIRS,
            "full_dataset_harness_repair_pairs": DEFAULT_FULL_DATASET_HARNESS_REPAIR_PAIRS,
            "benchmark_repair_pairs_fc128best": DEFAULT_BENCHMARK_REPAIR_PAIRS,
            "profile_default_out": str(default_out_for_profile(profile, repo=repo).relative_to(repo)),
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
            f"`{DEFAULT_FULL_DATASET_HARNESS_REPAIR_PAIRS}`, "
            f"and `{DEFAULT_BENCHMARK_REPAIR_PAIRS}`."
        ),
    )
    parser.add_argument("--profile", choices=VALID_PROFILES, default=DEFAULT_PROFILE)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    repair_pair_files = list(
        args.repair_pair_file
        or [
            DEFAULT_REPAIR_PAIRS,
            DEFAULT_LONG_RALPH_REPAIR_PAIRS,
            DEFAULT_SYNTHETIC_REPAIR_PAIRS,
            DEFAULT_FULL_DATASET_VALIDATED_REPAIR_PAIRS,
            DEFAULT_FULL_DATASET_HARNESS_REPAIR_PAIRS,
            DEFAULT_BENCHMARK_REPAIR_PAIRS,
        ]
    )
    out_path = args.out or default_out_for_profile(args.profile)
    rows, summary = build_corpus(repair_pair_files=repair_pair_files, profile=args.profile)
    _write_jsonl(out_path, rows)
    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out_path), "summary": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
