import json
from pathlib import Path

from scripts.build_tla_prover_corpus_experiment_matrix import build_report


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_report_summarizes_corpus_lanes_and_publish_blockers(tmp_path: Path) -> None:
    _write(
        tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        {
            "total_rows": 1330,
            "base_rows": 1053,
            "formalllm_rows": 205,
            "verified_tlaps_rows": 18,
            "verified_tlaps_weight": 4,
        },
    )
    _write(
        tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json",
        {
            "total_rows": 2503,
            "base_rows": 1053,
            "formalllm_rows": 205,
            "verified_tlaps_rows": 18,
            "verified_tlaps_weight": 4,
            "public_import_rows": 1005,
            "public_seed_candidates_rows": 168,
        },
    )
    _write(
        tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json",
        {
            "total_rows": 2508,
            "base_rows": 1053,
            "formalllm_rows": 205,
            "verified_tlaps_rows": 18,
            "verified_tlaps_weight": 4,
            "public_import_rows": 1010,
            "public_seed_candidates_rows": 168,
        },
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        {
            "rows": 541,
            "difficulty_counts": {"easy": 256, "medium": 61, "hard": 224},
            "health": {"ok": True, "warnings": [], "benchmark_only": False, "only_easy_rows": False},
            "kept_rows_by_source": {
                "data/processed/benchmark_repair_pairs_fc128best.jsonl": 20,
                "data/processed/tla_prover_synthetic_repair_pairs_v1.jsonl": 491,
                "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.jsonl": 22,
                "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.jsonl": 8,
            },
            "missing_sources": [
                "data/processed/ralph_repair_pairs.jsonl",
                "data/processed/ralph_repair_pairs_long_latest.jsonl",
            ],
        },
    )
    _write(
        tmp_path / "data/processed/benchmark_repair_pairs_fc128best.summary.json",
        {
            "rows": 20,
            "failed_rows_seen": 20,
            "gold_coverage": {"covered_failed_rows": 20, "missing_gold_benchmark_ids": []},
        },
    )
    _write(
        tmp_path / "data/processed/tla_prover_synthetic_repair_pairs_v1.summary.json",
        {
            "rows": 1009,
            "difficulty_counts": {"easy": 462, "medium": 128, "hard": 419},
        },
    )
    _write(
        tmp_path / "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.summary.json",
        {
            "rows": 22,
            "candidate_rows": 37,
            "validated_tier_counts": {"gold": 18, "silver": 5, "bronze": 6},
            "kept_by_bucket": {"proof_repair": 15, "inductiveness_repair": 3, "tlc_repair": 4},
        },
    )
    _write(
        tmp_path / "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.summary.json",
        {
            "rows": 8,
            "candidate_rows": 8,
            "validated_tier_counts": {"gold": 4, "silver": 4},
            "kept_by_bucket": {"skip_harness_repair": 8},
        },
    )
    _write(
        tmp_path / "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json",
        {
            "kept_rows": 168,
            "unique_modules": 114,
            "source_rows": 2108,
            "shape_ready_source_rows": 168,
        },
    )
    _write(
        tmp_path / "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json",
        {
            "kept_rows": 0,
            "unique_modules": 0,
            "source_rows": 2108,
            "shape_ready_source_rows": 168,
        },
    )
    _write(
        tmp_path / "outputs/manifests/ai4fm_public_seed_prover_funnel.json",
        {
            "funnel": {
                "source_rows": 2108,
                "shape_ready_rows": 168,
                "shape_ready_unique_modules": 114,
                "sany_clean_rows": 168,
                "shape_ready_but_not_sany_clean_rows": 0,
            }
        },
    )
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.json",
        {
            "benchmark_model": "chattla:20b",
            "ready_to_publish": False,
            "blockers": ["stale", "zero passes"],
            "benchmark": {
                "rows": 20,
                "sany": 0,
                "tlc": 0,
                "age_hours": 100.0,
                "source_path": "outputs/bench.csv",
            },
        },
    )
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {
            "benchmark_model": "chattla:20b-fc128best",
            "ready_to_publish": False,
            "blockers": ["zero passes"],
            "benchmark": {
                "rows": 20,
                "sany": 0,
                "tlc": 0,
                "age_hours": 2.0,
                "source_path": "outputs/bench-fc128.csv",
            },
        },
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_preflight.json",
        {
            "formalllm_coverage": {
                "formalllm_rows": 205,
                "ok": True,
                "corpora": [
                    {
                        "path": "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
                        "matched_distinct_rows": 205,
                        "matched_total_occurrences": 205,
                        "missing_rows": 0,
                        "extra_occurrences_over_formalllm_rows": 0,
                        "ok": True,
                    },
                    {
                        "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
                        "matched_distinct_rows": 205,
                        "matched_total_occurrences": 205,
                        "missing_rows": 0,
                        "extra_occurrences_over_formalllm_rows": 0,
                        "ok": True,
                    },
                    {
                        "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl",
                        "matched_distinct_rows": 205,
                        "matched_total_occurrences": 205,
                        "missing_rows": 0,
                        "extra_occurrences_over_formalllm_rows": 0,
                        "ok": True,
                    },
                ],
            },
            "diamond_eval_holdout_leakage": {
                "ok": True,
                "corpora": [
                    {
                        "path": "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
                        "leaked_rows": 0,
                        "ok": True,
                    },
                    {
                        "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
                        "leaked_rows": 0,
                        "ok": True,
                    },
                    {
                        "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl",
                        "leaked_rows": 0,
                        "ok": True,
                    },
                ],
            },
        },
    )
    _write(
        tmp_path / "outputs/manifests/ai4fm_public_tlaprove_corpora.json",
        {
            "aggregate": {
                "total_public_jsonl_rows": 2350,
                "all_public_jsonl_rows": 2757,
                "all_public_jsonl_files": 19,
            }
        },
    )
    _write(
        tmp_path / "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json",
        {"totals": {"tla": 2110}},
    )
    _write(
        tmp_path / "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json",
        {"rows": 2108},
    )
    _write(
        tmp_path / "outputs/manifests/ai4fm_public_dataset_surface.json",
        {
            "public_1800_plus_interpretation": {
                "canonical_formalllm_rows": 205,
                "status": "stale_for_formalllm_canonical_layer",
            }
        },
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_local_repair_plan.json",
        {
            "schema": "chattla_tla_prover_local_repair_plan_v1",
            "runtime_import_timeout_s": 10.0,
            "bootstrap_recommendation": {
                "reason": "selected_python_runtime_import_timeouts",
                "command": None,
                "message": "native import blocker",
                "selected_python": "/tmp/local/.venv/bin/python",
            },
            "preflight_report": {
                "ok": False,
                "runtime_dependencies": {
                    "ok": False,
                    "missing": [
                        {"module": "datasets.Dataset"},
                        {"module": "trl.GRPOTrainer"},
                    ],
                },
            },
        },
    )

    report = build_report(tmp_path)

    assert report["schema"] == "chattla_tla_prover_corpus_experiment_matrix_v1"
    assert report["publish_baseline_lane"] == "default"
    assert report["lanes"]["default"]["rows"] == 1330
    assert report["lanes"]["default"]["default_publish_lane"] is True
    assert report["lanes"]["default"]["formalllm_coverage"]["matched_distinct_rows"] == 205
    assert report["lanes"]["default"]["diamond_eval_holdout_leakage"]["leaked_rows"] == 0
    assert report["lanes"]["expanded"]["delta_vs_default_rows"] == 1173
    assert report["lanes"]["expanded"]["component_rows"]["public_import_rows"] == 1005
    assert report["lanes"]["full-public"]["delta_vs_default_rows"] == 1178
    assert report["lanes"]["shape-ready"]["trainable"] is False
    assert report["lanes"]["shape-ready"]["unique_modules"] == 114
    assert report["lanes"]["shape-ready-not-sany"]["delta_vs_shape_ready_rows"] == -168
    assert report["comparisons"]["full_public_vs_expanded_extra_rows"] == 5
    assert report["seed_funnel_snapshot"]["shape_ready_but_not_sany_clean_rows"] == 0
    assert report["formalllm_contract"]["canonical_rows"] == 205
    assert report["formalllm_contract"]["coverage_ok"] is True
    assert report["formalllm_contract"]["diamond_eval_holdout_leakage_ok"] is True
    assert report["public_ai4fm_scope"]["tracked_tlaprove_public_rows"] == 2350
    assert report["public_ai4fm_scope"]["all_public_tlaprove_rows"] == 2757
    assert report["public_ai4fm_scope"]["public_seed_tla_files"] == 2110
    assert report["public_ai4fm_scope"]["usable_public_seed_modules"] == 2108
    assert report["repair_corpus_status"]["rows"] == 541
    assert report["repair_corpus_status"]["sources"]["benchmark_fc128best"]["rows_in_merged_corpus"] == 20
    assert report["repair_corpus_status"]["sources"]["synthetic"]["rows_in_merged_corpus"] == 491
    assert report["repair_corpus_status"]["sources"]["full_dataset_validated"]["rows_in_merged_corpus"] == 22
    assert report["repair_corpus_status"]["sources"]["full_dataset_validated"]["candidate_rows"] == 37
    assert report["repair_corpus_status"]["sources"]["full_dataset_harness_repair"]["rows_in_merged_corpus"] == 8
    assert report["repair_corpus_status"]["sources"]["full_dataset_harness_repair"]["candidate_rows"] == 8
    assert report["repair_corpus_status"]["comparisons"]["strict_validated_rows_added_beyond_benchmark"] == 22
    assert report["repair_corpus_status"]["comparisons"]["harness_validated_rows_added_beyond_benchmark"] == 8
    assert report["repair_corpus_status"]["comparisons"]["validated_rows_added_beyond_benchmark"] == 30
    assert report["repair_corpus_status"]["comparisons"]["rows_beyond_benchmark_only"] == 521
    assert report["local_repair_runtime_status"] == {
        "path": "outputs/manifests/tla_prover_local_repair_plan.json",
        "present": True,
        "preflight_ok": False,
        "local_runtime_ready": False,
        "runtime_import_timeout_s": 10.0,
        "runtime_missing_modules": ["datasets.Dataset", "trl.GRPOTrainer"],
        "bootstrap_recommendation": {
            "reason": "selected_python_runtime_import_timeouts",
            "command": None,
            "message": "native import blocker",
        },
    }
    assert report["publish_readiness"]["default_model"]["benchmark_model"] == "chattla:20b"
    assert report["publish_readiness"]["fc128best_model"]["ready_to_publish"] is False
    assert report["named_corpora"]["full-public"].endswith("chattla_tla_prover_sft_public_all_v1.jsonl")
