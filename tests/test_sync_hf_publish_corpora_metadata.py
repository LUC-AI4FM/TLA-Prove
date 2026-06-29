import json
from pathlib import Path

from scripts.sync_hf_publish_corpora_metadata import build_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_sources(repo: Path) -> None:
    for bundle_name, source_rel in {
        "ai4fm_org_surface.json": "outputs/manifests/ai4fm_org_surface.json",
        "ai4fm_public_dataset_surface.json": "outputs/manifests/ai4fm_public_dataset_surface.json",
        "ai4fm_public_discovery_manifest_v1.summary.json": "data/processed/ai4fm_public_discovery_manifest_v1.summary.json",
        "benchmark_repair_pairs_fc128best.summary.json": "data/processed/benchmark_repair_pairs_fc128best.summary.json",
        "ai4fm_public_seed_file_manifest_v1.summary.json": "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json",
        "ai4fm_public_seed_license_surface.json": "outputs/manifests/ai4fm_public_seed_license_surface.json",
        "ai4fm_public_seed_tla_modules_v1.summary.json": "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json",
        "ai4fm_public_seed_prover_candidates_v1.summary.json": "data/processed/ai4fm_public_seed_prover_candidates_v1.summary.json",
        "ai4fm_public_seed_prover_shape_ready_v1.summary.json": "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json",
        "ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json": "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json",
        "ai4fm_public_tlaprove_corpora.json": "outputs/manifests/ai4fm_public_tlaprove_corpora.json",
        "ai4fm_public_tlaprove_import_all_public_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_all_public_v1.summary.json",
        "ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json",
        "chattla_tla_prover_sft_public_all_v1.summary.json": "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json",
        "ai4fm_public_tlaprove_import_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_v1.summary.json",
        "ai4fm_public_tlaprove_import_raw_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json",
        "chattla_tla_prover_sft_public_expanded_v1.summary.json": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json",
        "chattla_tla_prover_sft_v1.summary.json": "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        "formalllm_eval_v1.summary.json": "data/processed/formalllm_eval_v1.summary.json",
        "hf_publish_readiness.chattla_20b_fc128best.json": "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        "hf_publish_readiness.json": "outputs/manifests/hf_publish_readiness.json",
        "prover_eval.summary.json": "data/processed/prover_eval.summary.json",
        "sany_tlc_pass_corpus_diagnostic.json": "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json",
        "sany_tlc_pass_eval_v1.summary.json": "data/processed/sany_tlc_pass_eval_v1.summary.json",
        "sany_tlc_pass_sft_v1.summary.json": "data/processed/sany_tlc_pass_sft_v1.summary.json",
        "tla_prover_artifacts_v1.json": "outputs/manifests/tla_prover_artifacts_v1.json",
        "tla_prover_corpus_preflight.json": "outputs/manifests/tla_prover_corpus_preflight.json",
        "tla_prover_corpus_experiment_matrix.json": "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        "tla_prover_full_dataset_failure_analysis.json": "outputs/manifests/tla_prover_full_dataset_failure_analysis.json",
        "tlaps_verified_autoprover_traces_v1.summary.json": "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json",
    }.items():
        _write(repo / source_rel, json.dumps({"bundle_name": bundle_name}))


def test_build_report_syncs_bundle_metadata(tmp_path: Path) -> None:
    _write_sources(tmp_path)
    bundle_root = tmp_path / "outputs" / "hf_publish" / "chattla-tla-prover-corpora-v1"

    report = build_report(repo=tmp_path, bundle_root=bundle_root, write=True)

    assert report["ok"] is True
    assert report["missing_sources"] == []
    assert all(item["changed"] is True for item in report["copied"])
    target = bundle_root / "metadata" / "tla_prover_artifacts_v1.json"
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {"bundle_name": "tla_prover_artifacts_v1.json"}
    assert (bundle_root / "metadata" / "chattla_tla_prover_sft_public_expanded_v1.summary.json").exists()


def test_build_report_check_mode_detects_missing_sources_without_writing(tmp_path: Path) -> None:
    _write(tmp_path / "outputs/manifests/ai4fm_public_dataset_surface.json", "{}")
    bundle_root = tmp_path / "outputs" / "hf_publish" / "chattla-tla-prover-corpora-v1"

    report = build_report(repo=tmp_path, bundle_root=bundle_root, write=False)

    assert report["ok"] is False
    assert "data/processed/ai4fm_public_discovery_manifest_v1.summary.json" in report["missing_sources"]
    assert not (bundle_root / "metadata").exists()
