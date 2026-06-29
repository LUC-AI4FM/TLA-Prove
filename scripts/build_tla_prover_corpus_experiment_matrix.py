#!/usr/bin/env python3
"""Build a machine-readable matrix for bounded TLA prover corpus experiments."""
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

from scripts.tla_prover_corpus_paths import (
    DEFAULT_LOCAL_SFT_TRAIN,
    NAMED_SFT_CORPORA,
    resolve_named_sft_corpus,
)

DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_corpus_experiment_matrix.json"
DEFAULT_SUMMARY = "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json"
EXPANDED_SUMMARY = "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json"
FULL_PUBLIC_SUMMARY = "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json"
SHAPE_READY_SUMMARY = "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json"
SHAPE_READY_NOT_SANY_SUMMARY = (
    "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json"
)
FUNNEL_PATH = "outputs/manifests/ai4fm_public_seed_prover_funnel.json"
HF_READINESS_PATH = "outputs/manifests/hf_publish_readiness.json"
HF_READINESS_FC128BEST_PATH = "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json"


def _read_json(repo: Path, rel_path: str) -> dict[str, Any]:
    return json.loads((repo / rel_path).read_text(encoding="utf-8"))


def _lane_path(alias: str) -> str:
    if alias == "default":
        return DEFAULT_LOCAL_SFT_TRAIN
    resolved = resolve_named_sft_corpus(alias)
    if resolved is None:
        raise KeyError(f"unknown corpus alias: {alias}")
    return resolved


def _trainable_lane(
    *,
    alias: str,
    summary_path: str,
    summary: dict[str, Any],
    baseline_rows: int,
    default_publish: bool,
    intended_role: str,
) -> dict[str, Any]:
    rows = int(summary["total_rows"])
    lane: dict[str, Any] = {
        "alias": alias,
        "path": _lane_path(alias),
        "summary_path": summary_path,
        "rows": rows,
        "delta_vs_default_rows": rows - baseline_rows,
        "trainable": True,
        "default_publish_lane": default_publish,
        "intended_role": intended_role,
    }
    component_rows = {
        "base_rows": int(summary.get("base_rows", 0)),
        "formalllm_rows": int(summary.get("formalllm_rows", 0)),
        "verified_tlaps_rows": int(summary.get("verified_tlaps_rows", 0)),
        "verified_tlaps_weight": int(summary.get("verified_tlaps_weight", 0)),
    }
    if "public_import_rows" in summary:
        component_rows["public_import_rows"] = int(summary["public_import_rows"])
    if "public_seed_candidates_rows" in summary:
        component_rows["public_seed_candidates_rows"] = int(summary["public_seed_candidates_rows"])
    lane["component_rows"] = component_rows
    return lane


def _shape_lane(
    *,
    alias: str,
    summary_path: str,
    summary: dict[str, Any],
    funnel: dict[str, Any],
    intended_role: str,
) -> dict[str, Any]:
    funnel_rows = funnel["funnel"]
    rows = int(summary["kept_rows"])
    return {
        "alias": alias,
        "path": _lane_path(alias),
        "summary_path": summary_path,
        "rows": rows,
        "delta_vs_shape_ready_rows": rows - int(funnel_rows["shape_ready_rows"]),
        "unique_modules": int(summary["unique_modules"]),
        "source_rows": int(summary["source_rows"]),
        "shape_ready_source_rows": int(summary["shape_ready_source_rows"]),
        "sany_clean_rows": int(funnel_rows["sany_clean_rows"]),
        "trainable": False,
        "default_publish_lane": False,
        "intended_role": intended_role,
    }


def _readiness_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    benchmark = report.get("benchmark", {})
    return {
        "benchmark_model": report.get("benchmark_model"),
        "ready_to_publish": bool(report.get("ready_to_publish")),
        "blockers": list(report.get("blockers", [])),
        "rows": int(benchmark.get("rows", 0)),
        "sany": int(benchmark.get("sany", 0)),
        "tlc": int(benchmark.get("tlc", 0)),
        "age_hours": benchmark.get("age_hours"),
        "source_path": benchmark.get("source_path"),
    }


def build_report(repo: Path = REPO) -> dict[str, Any]:
    default_summary = _read_json(repo, DEFAULT_SUMMARY)
    expanded_summary = _read_json(repo, EXPANDED_SUMMARY)
    full_public_summary = _read_json(repo, FULL_PUBLIC_SUMMARY)
    shape_ready_summary = _read_json(repo, SHAPE_READY_SUMMARY)
    shape_ready_not_sany_summary = _read_json(repo, SHAPE_READY_NOT_SANY_SUMMARY)
    funnel = _read_json(repo, FUNNEL_PATH)
    readiness = _read_json(repo, HF_READINESS_PATH)
    readiness_fc128best = _read_json(repo, HF_READINESS_FC128BEST_PATH)

    baseline_rows = int(default_summary["total_rows"])
    expanded_rows = int(expanded_summary["total_rows"])
    full_public_rows = int(full_public_summary["total_rows"])
    shape_ready_rows = int(shape_ready_summary["kept_rows"])
    shape_ready_not_sany_rows = int(shape_ready_not_sany_summary["kept_rows"])

    lanes = {
        "default": _trainable_lane(
            alias="default",
            summary_path=DEFAULT_SUMMARY,
            summary=default_summary,
            baseline_rows=baseline_rows,
            default_publish=True,
            intended_role="current_publish_baseline",
        ),
        "expanded": _trainable_lane(
            alias="expanded",
            summary_path=EXPANDED_SUMMARY,
            summary=expanded_summary,
            baseline_rows=baseline_rows,
            default_publish=False,
            intended_role="bounded_public_comparison_train",
        ),
        "full-public": _trainable_lane(
            alias="full-public",
            summary_path=FULL_PUBLIC_SUMMARY,
            summary=full_public_summary,
            baseline_rows=baseline_rows,
            default_publish=False,
            intended_role="maximal_committed_public_comparison_train",
        ),
        "shape-ready": _shape_lane(
            alias="shape-ready",
            summary_path=SHAPE_READY_SUMMARY,
            summary=shape_ready_summary,
            funnel=funnel,
            intended_role="repair_and_prompt_shape_probe",
        ),
        "shape-ready-not-sany": _shape_lane(
            alias="shape-ready-not-sany",
            summary_path=SHAPE_READY_NOT_SANY_SUMMARY,
            summary=shape_ready_not_sany_summary,
            funnel=funnel,
            intended_role="repair_only_seed_lane",
        ),
    }

    return {
        "schema": "chattla_tla_prover_corpus_experiment_matrix_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": ".",
        "publish_baseline_lane": "default",
        "default_train_file": DEFAULT_LOCAL_SFT_TRAIN,
        "named_corpora": {"default": DEFAULT_LOCAL_SFT_TRAIN, **{k: v for k, v in NAMED_SFT_CORPORA.items() if v}},
        "lanes": lanes,
        "comparisons": {
            "expanded_vs_default_extra_rows": expanded_rows - baseline_rows,
            "full_public_vs_default_extra_rows": full_public_rows - baseline_rows,
            "full_public_vs_expanded_extra_rows": full_public_rows - expanded_rows,
            "shape_ready_vs_sany_clean_extra_rows": (
                shape_ready_rows - int(funnel["funnel"]["sany_clean_rows"])
            ),
            "shape_ready_not_sany_rows": shape_ready_not_sany_rows,
        },
        "seed_funnel_snapshot": {
            "source_rows": int(funnel["funnel"]["source_rows"]),
            "shape_ready_rows": int(funnel["funnel"]["shape_ready_rows"]),
            "shape_ready_unique_modules": int(funnel["funnel"]["shape_ready_unique_modules"]),
            "sany_clean_rows": int(funnel["funnel"]["sany_clean_rows"]),
            "shape_ready_but_not_sany_clean_rows": int(
                funnel["funnel"]["shape_ready_but_not_sany_clean_rows"]
            ),
        },
        "publish_readiness": {
            "default_model": _readiness_snapshot(readiness),
            "fc128best_model": _readiness_snapshot(readiness_fc128best),
        },
        "promotion_gates": [
            "Keep the default lane as the publish baseline until a fresh benchmarked model shows non-zero SANY or TLC passes without regressions.",
            "Use the expanded and full-public lanes for bounded comparison runs first; do not publish from those lanes on corpus size alone.",
            "Use the shape-ready and shape-ready-not-sany lanes only for repair, curriculum, or ablation work; they are not publish lanes.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report(args.repo)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
