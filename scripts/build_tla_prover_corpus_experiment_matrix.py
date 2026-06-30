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
REPAIR_TRAIN_SUMMARY = "data/processed/tla_prover_repair_train_v1.summary.json"
BENCHMARK_REPAIR_SUMMARY = "data/processed/benchmark_repair_pairs_fc128best.summary.json"
SYNTHETIC_REPAIR_SUMMARY = "data/processed/tla_prover_synthetic_repair_pairs_v1.summary.json"
FULL_DATASET_VALIDATED_REPAIR_SUMMARY = (
    "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.summary.json"
)
FULL_DATASET_HARNESS_REPAIR_SUMMARY = (
    "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.summary.json"
)
SHAPE_READY_SUMMARY = "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json"
SHAPE_READY_NOT_SANY_SUMMARY = (
    "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json"
)
FUNNEL_PATH = "outputs/manifests/ai4fm_public_seed_prover_funnel.json"
HF_READINESS_PATH = "outputs/manifests/hf_publish_readiness.json"
HF_READINESS_FC128BEST_PATH = "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json"
CORPUS_PREFLIGHT_PATH = "outputs/manifests/tla_prover_corpus_preflight.json"
PUBLIC_TLAPROVE_PATH = "outputs/manifests/ai4fm_public_tlaprove_corpora.json"
SEED_FILE_SUMMARY = "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json"
SEED_MODULE_SUMMARY = "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json"
DATASET_SURFACE_PATH = "outputs/manifests/ai4fm_public_dataset_surface.json"
LOCAL_REPAIR_PLAN_PATH = "outputs/manifests/tla_prover_local_repair_plan.json"


def _read_json(repo: Path, rel_path: str) -> dict[str, Any]:
    return json.loads((repo / rel_path).read_text(encoding="utf-8"))


def _read_optional_json(repo: Path, rel_path: str) -> dict[str, Any] | None:
    path = repo / rel_path
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _compact_bootstrap_recommendation(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {
        key: value.get(key)
        for key in ("reason", "command", "message")
        if key in value
    }
    return compact or None


def _local_repair_runtime_status(repo: Path) -> dict[str, Any]:
    payload = _read_optional_json(repo, LOCAL_REPAIR_PLAN_PATH)
    if not isinstance(payload, dict):
        return {"path": LOCAL_REPAIR_PLAN_PATH, "present": False}
    preflight_report = dict(payload.get("preflight_report") or {})
    runtime_dependencies = dict(preflight_report.get("runtime_dependencies") or {})
    runtime_missing_modules = [
        str(entry.get("module"))
        for entry in list(runtime_dependencies.get("missing") or [])
        if str(entry.get("module") or "").strip()
    ]
    return {
        "path": LOCAL_REPAIR_PLAN_PATH,
        "present": True,
        "preflight_ok": preflight_report.get("ok"),
        "local_runtime_ready": runtime_dependencies.get("ok"),
        "runtime_import_timeout_s": payload.get("runtime_import_timeout_s"),
        "runtime_missing_modules": runtime_missing_modules,
        "bootstrap_recommendation": _compact_bootstrap_recommendation(
            payload.get("bootstrap_recommendation")
        ),
    }


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


def _coverage_by_path(preflight: dict[str, Any]) -> dict[str, dict[str, Any]]:
    coverage = preflight.get("formalllm_coverage", {})
    corpora = coverage.get("corpora", []) if isinstance(coverage, dict) else []
    by_path: dict[str, dict[str, Any]] = {}
    for item in corpora:
        if isinstance(item, dict):
            path = item.get("path")
            if isinstance(path, str) and path:
                by_path[path] = item
    return by_path


def _holdout_leakage_by_path(preflight: dict[str, Any]) -> dict[str, dict[str, Any]]:
    leakage = preflight.get("diamond_eval_holdout_leakage", {})
    corpora = leakage.get("corpora", []) if isinstance(leakage, dict) else []
    by_path: dict[str, dict[str, Any]] = {}
    for item in corpora:
        if isinstance(item, dict):
            path = item.get("path")
            if isinstance(path, str) and path:
                by_path[path] = item
    return by_path


def _attach_train_lane_contract(
    lane: dict[str, Any],
    *,
    coverage_by_path: dict[str, dict[str, Any]],
    holdout_by_path: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    path = str(lane["path"])
    coverage = coverage_by_path.get(path)
    if coverage is not None:
        lane["formalllm_coverage"] = {
            "matched_distinct_rows": int(coverage.get("matched_distinct_rows", 0)),
            "matched_total_occurrences": int(coverage.get("matched_total_occurrences", 0)),
            "missing_rows": int(coverage.get("missing_rows", 0)),
            "extra_occurrences_over_formalllm_rows": int(
                coverage.get("extra_occurrences_over_formalllm_rows", 0)
            ),
            "ok": bool(coverage.get("ok")),
        }
    leakage = holdout_by_path.get(path)
    if leakage is not None:
        lane["diamond_eval_holdout_leakage"] = {
            "leaked_rows": int(leakage.get("leaked_rows", 0)),
            "ok": bool(leakage.get("ok")),
        }
    return lane


def _repair_source_rows(repair_summary: dict[str, Any], path: str) -> int:
    source_rows = dict(repair_summary.get("kept_rows_by_source") or {})
    return int(source_rows.get(path, 0) or 0)


def _repair_corpus_status(
    *,
    repair_summary: dict[str, Any],
    benchmark_summary: dict[str, Any],
    synthetic_summary: dict[str, Any],
    full_dataset_validated_summary: dict[str, Any],
    full_dataset_harness_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    benchmark_path = "data/processed/benchmark_repair_pairs_fc128best.jsonl"
    synthetic_path = "data/processed/tla_prover_synthetic_repair_pairs_v1.jsonl"
    full_dataset_path = "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.jsonl"
    full_dataset_harness_path = "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.jsonl"
    benchmark_rows = _repair_source_rows(repair_summary, benchmark_path)
    synthetic_rows = _repair_source_rows(repair_summary, synthetic_path)
    full_dataset_rows = _repair_source_rows(repair_summary, full_dataset_path)
    full_dataset_harness_rows = _repair_source_rows(repair_summary, full_dataset_harness_path)
    total_rows = int(repair_summary.get("rows", 0) or 0)
    combined_validated_rows = full_dataset_rows + full_dataset_harness_rows
    harness_summary = full_dataset_harness_summary or {}
    return {
        "path": "data/processed/tla_prover_repair_train_v1.jsonl",
        "summary_path": REPAIR_TRAIN_SUMMARY,
        "rows": total_rows,
        "difficulty_counts": dict(repair_summary.get("difficulty_counts") or {}),
        "health": dict(repair_summary.get("health") or {}),
        "missing_sources": list(repair_summary.get("missing_sources") or []),
        "sources": {
            "benchmark_fc128best": {
                "rows_in_merged_corpus": benchmark_rows,
                "source_rows": int(benchmark_summary.get("rows", 0) or 0),
                "failed_rows_seen": benchmark_summary.get("failed_rows_seen"),
                "covered_failed_rows": dict(benchmark_summary.get("gold_coverage") or {}).get("covered_failed_rows"),
                "missing_gold_benchmark_ids": list(
                    dict(benchmark_summary.get("gold_coverage") or {}).get("missing_gold_benchmark_ids", [])
                ),
            },
            "synthetic": {
                "rows_in_merged_corpus": synthetic_rows,
                "source_rows": int(synthetic_summary.get("rows", 0) or 0),
                "difficulty_counts": dict(synthetic_summary.get("difficulty_counts") or {}),
            },
            "full_dataset_validated": {
                "rows_in_merged_corpus": full_dataset_rows,
                "source_rows": int(full_dataset_validated_summary.get("rows", 0) or 0),
                "candidate_rows": full_dataset_validated_summary.get("candidate_rows"),
                "validated_tier_counts": dict(full_dataset_validated_summary.get("validated_tier_counts") or {}),
                "kept_by_bucket": dict(full_dataset_validated_summary.get("kept_by_bucket") or {}),
            },
            "full_dataset_harness_repair": {
                "rows_in_merged_corpus": full_dataset_harness_rows,
                "source_rows": int(harness_summary.get("rows", 0) or 0),
                "candidate_rows": harness_summary.get("candidate_rows"),
                "validated_tier_counts": dict(harness_summary.get("validated_tier_counts") or {}),
                "kept_by_bucket": dict(harness_summary.get("kept_by_bucket") or {}),
            },
        },
        "comparisons": {
            "rows_beyond_benchmark_only": total_rows - benchmark_rows,
            "strict_validated_rows_added_beyond_benchmark": full_dataset_rows,
            "harness_validated_rows_added_beyond_benchmark": full_dataset_harness_rows,
            "validated_rows_added_beyond_benchmark": combined_validated_rows,
            "synthetic_rows_added_beyond_benchmark": synthetic_rows,
        },
    }


def build_report(repo: Path = REPO) -> dict[str, Any]:
    default_summary = _read_json(repo, DEFAULT_SUMMARY)
    expanded_summary = _read_json(repo, EXPANDED_SUMMARY)
    full_public_summary = _read_json(repo, FULL_PUBLIC_SUMMARY)
    repair_summary = _read_json(repo, REPAIR_TRAIN_SUMMARY)
    benchmark_repair_summary = _read_json(repo, BENCHMARK_REPAIR_SUMMARY)
    synthetic_repair_summary = _read_json(repo, SYNTHETIC_REPAIR_SUMMARY)
    full_dataset_validated_repair_summary = _read_json(repo, FULL_DATASET_VALIDATED_REPAIR_SUMMARY)
    full_dataset_harness_repair_summary = _read_optional_json(repo, FULL_DATASET_HARNESS_REPAIR_SUMMARY)
    shape_ready_summary = _read_json(repo, SHAPE_READY_SUMMARY)
    shape_ready_not_sany_summary = _read_json(repo, SHAPE_READY_NOT_SANY_SUMMARY)
    funnel = _read_json(repo, FUNNEL_PATH)
    readiness = _read_json(repo, HF_READINESS_PATH)
    readiness_fc128best = _read_json(repo, HF_READINESS_FC128BEST_PATH)
    preflight = _read_json(repo, CORPUS_PREFLIGHT_PATH)
    tlaprove = _read_json(repo, PUBLIC_TLAPROVE_PATH)
    seed_files = _read_json(repo, SEED_FILE_SUMMARY)
    seed_modules = _read_json(repo, SEED_MODULE_SUMMARY)
    dataset_surface = _read_json(repo, DATASET_SURFACE_PATH)

    baseline_rows = int(default_summary["total_rows"])
    expanded_rows = int(expanded_summary["total_rows"])
    full_public_rows = int(full_public_summary["total_rows"])
    shape_ready_rows = int(shape_ready_summary["kept_rows"])
    shape_ready_not_sany_rows = int(shape_ready_not_sany_summary["kept_rows"])
    coverage_by_path = _coverage_by_path(preflight)
    holdout_by_path = _holdout_leakage_by_path(preflight)
    formalllm_coverage_summary = preflight.get("formalllm_coverage", {})
    holdout_leakage_summary = preflight.get("diamond_eval_holdout_leakage", {})

    lanes = {
        "default": _attach_train_lane_contract(_trainable_lane(
            alias="default",
            summary_path=DEFAULT_SUMMARY,
            summary=default_summary,
            baseline_rows=baseline_rows,
            default_publish=True,
            intended_role="current_publish_baseline",
        ), coverage_by_path=coverage_by_path, holdout_by_path=holdout_by_path),
        "expanded": _attach_train_lane_contract(_trainable_lane(
            alias="expanded",
            summary_path=EXPANDED_SUMMARY,
            summary=expanded_summary,
            baseline_rows=baseline_rows,
            default_publish=False,
            intended_role="bounded_public_comparison_train",
        ), coverage_by_path=coverage_by_path, holdout_by_path=holdout_by_path),
        "full-public": _attach_train_lane_contract(_trainable_lane(
            alias="full-public",
            summary_path=FULL_PUBLIC_SUMMARY,
            summary=full_public_summary,
            baseline_rows=baseline_rows,
            default_publish=False,
            intended_role="maximal_committed_public_comparison_train",
        ), coverage_by_path=coverage_by_path, holdout_by_path=holdout_by_path),
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
        "formalllm_contract": {
            "canonical_rows": int(formalllm_coverage_summary.get("formalllm_rows", 0)),
            "coverage_ok": bool(formalllm_coverage_summary.get("ok")),
            "diamond_eval_holdout_leakage_ok": bool(holdout_leakage_summary.get("ok")),
            "default_train_path": DEFAULT_LOCAL_SFT_TRAIN,
        },
        "public_ai4fm_scope": {
            "canonical_formalllm_rows": int(
                dataset_surface["public_1800_plus_interpretation"]["canonical_formalllm_rows"]
            ),
            "tracked_tlaprove_public_rows": int(tlaprove["aggregate"]["total_public_jsonl_rows"]),
            "all_public_tlaprove_rows": int(tlaprove["aggregate"]["all_public_jsonl_rows"]),
            "all_public_tlaprove_files": int(tlaprove["aggregate"]["all_public_jsonl_files"]),
            "public_seed_tla_files": int(seed_files["totals"]["tla"]),
            "usable_public_seed_modules": int(seed_modules.get("rows", seed_modules.get("kept_rows", 0))),
            "interpretation_status": dataset_surface["public_1800_plus_interpretation"]["status"],
        },
        "repair_corpus_status": _repair_corpus_status(
        repair_summary=repair_summary,
        benchmark_summary=benchmark_repair_summary,
        synthetic_summary=synthetic_repair_summary,
        full_dataset_validated_summary=full_dataset_validated_repair_summary,
        full_dataset_harness_summary=full_dataset_harness_repair_summary,
    ),
        "local_repair_runtime_status": _local_repair_runtime_status(repo),
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
