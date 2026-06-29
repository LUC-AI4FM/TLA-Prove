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
            "total_rows": 2485,
            "base_rows": 1053,
            "formalllm_rows": 205,
            "verified_tlaps_rows": 18,
            "verified_tlaps_weight": 4,
            "public_import_rows": 1005,
            "public_seed_candidates_rows": 150,
        },
    )
    _write(
        tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json",
        {
            "total_rows": 2490,
            "base_rows": 1053,
            "formalllm_rows": 205,
            "verified_tlaps_rows": 18,
            "verified_tlaps_weight": 4,
            "public_import_rows": 1010,
            "public_seed_candidates_rows": 150,
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
            "kept_rows": 18,
            "unique_modules": 16,
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
                "sany_clean_rows": 150,
                "shape_ready_but_not_sany_clean_rows": 18,
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

    report = build_report(tmp_path)

    assert report["schema"] == "chattla_tla_prover_corpus_experiment_matrix_v1"
    assert report["publish_baseline_lane"] == "default"
    assert report["lanes"]["default"]["rows"] == 1330
    assert report["lanes"]["default"]["default_publish_lane"] is True
    assert report["lanes"]["expanded"]["delta_vs_default_rows"] == 1155
    assert report["lanes"]["expanded"]["component_rows"]["public_import_rows"] == 1005
    assert report["lanes"]["full-public"]["delta_vs_default_rows"] == 1160
    assert report["lanes"]["shape-ready"]["trainable"] is False
    assert report["lanes"]["shape-ready"]["unique_modules"] == 114
    assert report["lanes"]["shape-ready-not-sany"]["delta_vs_shape_ready_rows"] == -150
    assert report["comparisons"]["full_public_vs_expanded_extra_rows"] == 5
    assert report["seed_funnel_snapshot"]["shape_ready_but_not_sany_clean_rows"] == 18
    assert report["publish_readiness"]["default_model"]["benchmark_model"] == "chattla:20b"
    assert report["publish_readiness"]["fc128best_model"]["ready_to_publish"] is False
    assert report["named_corpora"]["full-public"].endswith("chattla_tla_prover_sft_public_all_v1.jsonl")
