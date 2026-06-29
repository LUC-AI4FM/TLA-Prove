import json
from pathlib import Path

from scripts.build_tla_prover_manifest import build_manifest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_manifest_summarizes_present_artifacts(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "outputs/manifests").mkdir(parents=True, exist_ok=True)
    (repo / "outputs/manifests/ai4fm_public_dataset_surface.json").write_text(
        json.dumps({"formalllm": {"canonical_entries": 205}, "pipeline": {"pull": {"nfiles": 2628}}}),
        encoding="utf-8",
    )
    (repo / "outputs/manifests/ai4fm_public_tlaprove_corpora.json").write_text(
        json.dumps({"aggregate": {"total_public_jsonl_rows": 2350}}),
        encoding="utf-8",
    )
    (repo / "outputs/manifests/ai4fm_org_surface.json").write_text(
        json.dumps({"public_repo_count": 8, "summary": {"corpus_relevant_repo_count": 3}}),
        encoding="utf-8",
    )
    (repo / "outputs/manifests/ai4fm_public_seed_license_surface.json").write_text(
        json.dumps({"license_summary": {"repo_counts": {"MIT": 1, "UNKNOWN": 1}}}),
        encoding="utf-8",
    )
    (repo / "outputs/manifests/ai4fm_public_seed_prover_funnel.json").write_text(
        json.dumps({"funnel": {"source_rows": 2, "shape_ready_rows": 1, "sany_clean_rows": 1}}),
        encoding="utf-8",
    )
    (repo / "outputs/manifests/hf_publish_readiness.json").write_text(
        json.dumps({"ready_to_publish": False, "next_publish_version": 22}),
        encoding="utf-8",
    )
    (repo / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json").write_text(
        json.dumps({"benchmark_model": "chattla:20b-fc128best", "ready_to_publish": False}),
        encoding="utf-8",
    )
    (repo / "outputs/manifests/tla_prover_corpus_experiment_matrix.json").write_text(
        json.dumps({"schema": "chattla_tla_prover_corpus_experiment_matrix_v1", "publish_baseline_lane": "default"}),
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "data/processed/ai4fm_public_tlaprove_import_v1.jsonl",
        [{"messages": []}, {"messages": []}, {"messages": []}, {"messages": []}],
    )
    (repo / "data/processed/ai4fm_public_tlaprove_import_v1.summary.json").write_text(
        json.dumps({"kept_rows": 4, "duplicate_rows_collapsed": 2}),
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "data/processed/ai4fm_public_tlaprove_import_raw_v1.jsonl",
        [{"messages": []}, {"messages": []}, {"messages": []}, {"messages": []}, {"messages": []}],
    )
    (repo / "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json").write_text(
        json.dumps({"kept_rows": 5, "duplicate_rows_collapsed": 0, "dedupe_exact_final_spec": False}),
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "data/processed/ai4fm_public_tlaprove_import_all_public_v1.jsonl",
        [{"messages": []}] * 6,
    )
    (repo / "data/processed/ai4fm_public_tlaprove_import_all_public_v1.summary.json").write_text(
        json.dumps({"kept_rows": 6, "duplicate_rows_collapsed": 3, "include_additional_public_jsonl": True}),
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "data/processed/ai4fm_public_tlaprove_import_all_public_raw_v1.jsonl",
        [{"messages": []}] * 9,
    )
    (repo / "data/processed/ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json").write_text(
        json.dumps({"kept_rows": 9, "duplicate_rows_collapsed": 0, "dedupe_exact_final_spec": False, "include_additional_public_jsonl": True}),
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "data/processed/ai4fm_public_seed_file_manifest_v1.jsonl",
        [{"repo": "a/b", "path": "SpecA.tla"}, {"repo": "a/b", "path": "SpecA.cfg"}],
    )
    (repo / "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json").write_text(
        json.dumps({"kept_rows": 2, "totals": {"all": 2, "tla": 1, "cfg": 1, "tlaps": 0}}),
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "data/processed/ai4fm_public_seed_tla_modules_v1.jsonl",
        [{"module": "SpecA", "repo": "a/b", "source_path": "SpecA.tla", "content": "---- MODULE SpecA ----\n====\n"}],
    )
    (repo / "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json").write_text(
        json.dumps({"kept_rows": 1, "duplicate_modules": {}}),
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "data/processed/ai4fm_public_seed_prover_candidates_v1.jsonl",
        [{"module": "SpecA", "repo": "a/b", "source_path": "SpecA.tla", "content": "---- MODULE SpecA ----\n====\n"}],
    )
    (repo / "data/processed/ai4fm_public_seed_prover_candidates_v1.summary.json").write_text(
        json.dumps({"kept_rows": 1, "skipped": {"sany_invalid": 2}}),
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "data/processed/ai4fm_public_seed_prover_shape_ready_v1.jsonl",
        [{"module": "SpecA", "repo": "a/b", "source_path": "SpecA.tla", "content": "---- MODULE SpecA ----\n====\n"}],
    )
    (repo / "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json").write_text(
        json.dumps({"kept_rows": 1, "unique_modules": 1}),
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.jsonl",
        [{"module": "SpecB", "repo": "a/b", "source_path": "SpecB.tla", "content": "---- MODULE SpecB ----\n====\n"}],
    )
    (repo / "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json").write_text(
        json.dumps({"kept_rows": 1, "excluded_sany_clean_rows": 1}),
        encoding="utf-8",
    )
    _write_jsonl(repo / "data/processed/ai4fm_public_discovery_manifest_v1.jsonl", [{"repo": "a/b"}])
    (repo / "data/processed/ai4fm_public_discovery_manifest_v1.summary.json").write_text(
        json.dumps({"unique_repo_records": 1}),
        encoding="utf-8",
    )
    _write_jsonl(repo / "data/processed/formalllm_eval_v1.jsonl", [{"messages": []}, {"messages": []}, {"messages": []}])
    _write_jsonl(repo / "data/processed/sany_tlc_pass_sft_v1.jsonl", [{"a": 1}, {"a": 2}])
    _write_jsonl(repo / "data/processed/prover_eval.jsonl", [{"messages": []}])
    _write_jsonl(repo / "data/processed/sany_tlc_pass_eval_v1.jsonl", [{"messages": []}, {"messages": []}])
    _write_jsonl(repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl", [{"messages": []}] * 5)
    (repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json").write_text(
        json.dumps({"total_rows": 5, "public_import_rows": 2, "public_seed_candidates_rows": 1}),
        encoding="utf-8",
    )
    _write_jsonl(repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl", [{"messages": []}] * 6)
    (repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json").write_text(
        json.dumps({"total_rows": 6, "public_import_rows": 3, "public_seed_candidates_rows": 1}),
        encoding="utf-8",
    )
    (repo / "data/processed/sany_tlc_pass_sft_v1.summary.json").write_text(
        json.dumps({"kept_rows": 2}),
        encoding="utf-8",
    )
    (repo / "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json").write_text(
        json.dumps({"ok": True, "rows": 2}),
        encoding="utf-8",
    )
    _write_jsonl(repo / "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl", [{"b": 1}])
    (repo / "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json").write_text(
        json.dumps({"raw_proved": 3, "raw_total": 3}),
        encoding="utf-8",
    )

    manifest = build_manifest(repo)

    assert manifest["schema"] == "chattla_tla_prover_artifacts_v1"
    assert manifest["artifacts"]["sany_tlc_pass_sft_v1"]["rows"] == 2
    assert manifest["artifacts"]["formalllm_eval_v1"]["rows"] == 3
    assert manifest["artifacts"]["formalllm_eval_v1"]["kind"] == "full_formalllm_prompt_eval_dataset"
    assert manifest["artifacts"]["chattla_tla_prover_sft_public_expanded_v1"]["exists"] is True
    assert manifest["artifacts"]["chattla_tla_prover_sft_public_expanded_v1"]["rows"] == 5
    assert manifest["artifacts"]["chattla_tla_prover_sft_public_expanded_v1"]["summary"]["public_import_rows"] == 2
    assert manifest["artifacts"]["chattla_tla_prover_sft_public_all_v1"]["exists"] is True
    assert manifest["artifacts"]["chattla_tla_prover_sft_public_all_v1"]["rows"] == 6
    assert manifest["artifacts"]["chattla_tla_prover_sft_public_all_v1"]["summary"]["public_import_rows"] == 3
    assert manifest["artifacts"]["ai4fm_public_dataset_surface"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_dataset_surface"]["kind"] == "public_ai4fm_dataset_surface_report"
    assert manifest["artifacts"]["ai4fm_public_tlaprove_corpora"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_tlaprove_corpora"]["kind"] == "public_ai4fm_tlaprove_corpora_report"
    assert manifest["artifacts"]["ai4fm_org_surface"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_org_surface"]["kind"] == "public_ai4fm_org_surface_report"
    assert manifest["artifacts"]["hf_publish_readiness"]["exists"] is True
    assert manifest["artifacts"]["hf_publish_readiness"]["kind"] == "model_hf_publish_readiness_report"
    assert manifest["artifacts"]["hf_publish_readiness_fc128best"]["exists"] is True
    assert manifest["artifacts"]["hf_publish_readiness_fc128best"]["kind"] == (
        "model_hf_publish_readiness_report"
    )
    assert manifest["artifacts"]["tla_prover_corpus_experiment_matrix"]["exists"] is True
    assert manifest["artifacts"]["tla_prover_corpus_experiment_matrix"]["kind"] == (
        "corpus_experiment_matrix_report"
    )
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_v1"]["rows"] == 4
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_v1"]["summary"]["duplicate_rows_collapsed"] == 2
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_raw_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_raw_v1"]["rows"] == 5
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_raw_v1"]["summary"]["dedupe_exact_final_spec"] is False
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_all_public_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_all_public_v1"]["rows"] == 6
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_all_public_v1"]["summary"]["include_additional_public_jsonl"] is True
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_all_public_raw_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_all_public_raw_v1"]["rows"] == 9
    assert manifest["artifacts"]["ai4fm_public_tlaprove_import_all_public_raw_v1"]["summary"]["dedupe_exact_final_spec"] is False
    assert manifest["artifacts"]["ai4fm_public_seed_file_manifest_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_seed_file_manifest_v1"]["rows"] == 2
    assert manifest["artifacts"]["ai4fm_public_seed_file_manifest_v1"]["summary"]["totals"]["tla"] == 1
    assert manifest["artifacts"]["ai4fm_public_seed_license_surface"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_seed_license_surface"]["kind"] == (
        "public_ai4fm_seed_repo_license_surface_report"
    )
    assert manifest["artifacts"]["ai4fm_public_seed_prover_funnel"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_seed_prover_funnel"]["kind"] == (
        "public_ai4fm_seed_repo_prover_funnel_report"
    )
    assert manifest["artifacts"]["ai4fm_public_seed_tla_modules_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_seed_tla_modules_v1"]["rows"] == 1
    assert manifest["artifacts"]["ai4fm_public_seed_tla_modules_v1"]["kind"] == (
        "public_ai4fm_seed_repo_tla_module_corpus"
    )
    assert manifest["artifacts"]["ai4fm_public_seed_prover_candidates_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_seed_prover_candidates_v1"]["rows"] == 1
    assert manifest["artifacts"]["ai4fm_public_seed_prover_candidates_v1"]["summary"]["skipped"]["sany_invalid"] == 2
    assert manifest["artifacts"]["ai4fm_public_seed_prover_shape_ready_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_seed_prover_shape_ready_v1"]["rows"] == 1
    assert manifest["artifacts"]["ai4fm_public_seed_prover_shape_ready_v1"]["kind"] == (
        "public_ai4fm_seed_repo_autoprover_shape_corpus"
    )
    assert manifest["artifacts"]["ai4fm_public_seed_prover_shape_ready_not_sany_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_seed_prover_shape_ready_not_sany_v1"]["rows"] == 1
    assert manifest["artifacts"]["ai4fm_public_seed_prover_shape_ready_not_sany_v1"]["summary"][
        "excluded_sany_clean_rows"
    ] == 1
    assert manifest["artifacts"]["ai4fm_public_discovery_manifest_v1"]["exists"] is True
    assert manifest["artifacts"]["ai4fm_public_discovery_manifest_v1"]["rows"] == 1
    assert manifest["artifacts"]["ai4fm_public_discovery_manifest_v1"]["kind"] == "public_ai4fm_repo_discovery_manifest"
    assert manifest["artifacts"]["prover_eval_v1"]["rows"] == 1
    assert manifest["artifacts"]["prover_eval_v1"]["kind"] == "verified_tlaps_prover_eval_dataset"
    assert manifest["artifacts"]["sany_tlc_pass_eval_v1"]["rows"] == 2
    assert manifest["artifacts"]["sany_tlc_pass_eval_v1"]["kind"] == "heldout_sany_tlc_pass_eval_dataset"
    assert manifest["artifacts"]["sany_tlc_pass_corpus_diagnostic"]["exists"] is True
    assert manifest["artifacts"]["sany_tlc_pass_corpus_diagnostic"]["kind"] == (
        "sany_tlc_pass_corpus_quality_gate"
    )
    assert manifest["artifacts"]["tlaps_verified_autoprover_traces_v1"]["rows"] == 1
    assert manifest["artifacts"]["tlaps_verified_autoprover_traces_v1"]["summary"]["raw_total"] == 3
    assert manifest["remote_next_steps"]["known18_pbs"] == "scripts/qsub_autoprover_known18_corrected_smoke.pbs"
    assert manifest["remote_next_steps"]["evaluate_remote_results"] == "python3 scripts/evaluate_tla_prover_remote_results.py"
    assert manifest["remote_next_steps"]["remote_decision_report"] == "outputs/manifests/tla_prover_remote_decision.json"
    assert manifest["remote_next_steps"]["probe_control_planes"] == "python3 scripts/probe_tla_prover_control_planes.py"
    assert manifest["remote_next_steps"]["diagnose_sany_tlc_pass_corpus"] == (
        "python3 scripts/diagnose_sany_tlc_pass_corpus.py"
    )
    assert manifest["remote_next_steps"]["build_tla_prover_corpus_experiment_matrix"] == (
        "python3 scripts/build_tla_prover_corpus_experiment_matrix.py"
    )
    assert manifest["remote_next_steps"]["pr_ready_check"] == "python3 scripts/check_tla_prover_pr_ready.py"
    assert manifest["remote_next_steps"]["build_tla_prover_eval_corpus"] == (
        "python3 scripts/build_tla_prover_eval_corpus.py"
    )
    assert manifest["remote_next_steps"]["inspect_ai4fm_public_dataset_surface"] == (
        "python3 scripts/inspect_ai4fm_public_dataset_surface.py"
    )
    assert manifest["remote_next_steps"]["inspect_ai4fm_public_seed_prover_funnel"] == (
        "python3 scripts/inspect_ai4fm_public_seed_prover_funnel.py"
    )
    assert manifest["remote_next_steps"]["inspect_ai4fm_public_tlaprove_corpora"] == (
        "python3 scripts/inspect_ai4fm_public_tlaprove_corpora.py"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_tlaprove_import"] == (
        "python3 scripts/build_ai4fm_public_tlaprove_import.py"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_tlaprove_import_raw"] == (
        "python3 scripts/build_ai4fm_public_tlaprove_import.py --keep-duplicates "
        "--out data/processed/ai4fm_public_tlaprove_import_raw_v1.jsonl"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_tlaprove_import_all_public"] == (
        "python3 scripts/build_ai4fm_public_tlaprove_import.py "
        "--include-additional-public-jsonl "
        "--out data/processed/ai4fm_public_tlaprove_import_all_public_v1.jsonl"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_tlaprove_import_all_public_raw"] == (
        "python3 scripts/build_ai4fm_public_tlaprove_import.py "
        "--include-additional-public-jsonl --keep-duplicates "
        "--out data/processed/ai4fm_public_tlaprove_import_all_public_raw_v1.jsonl"
    )
    assert manifest["remote_next_steps"]["build_tla_prover_finetune_corpus_public_all"] == (
        "python3 scripts/build_tla_prover_finetune_corpus.py "
        "--public-import data/processed/ai4fm_public_tlaprove_import_all_public_v1.jsonl "
        "--public-import-weight 1 --public-seed-candidates-weight 1 "
        "--out data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl"
    )
    assert manifest["remote_next_steps"]["inspect_ai4fm_org_surface"] == (
        "python3 scripts/inspect_ai4fm_org_surface.py"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_seed_file_manifest"] == (
        "python3 scripts/build_ai4fm_public_seed_file_manifest.py"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_seed_license_manifest"] == (
        "python3 scripts/build_ai4fm_public_seed_license_manifest.py"
    )
    assert manifest["remote_next_steps"]["sync_hf_publish_corpora_metadata"] == (
        "python3 scripts/sync_hf_publish_corpora_metadata.py"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_seed_tla_modules"] == (
        "python3 scripts/build_ai4fm_public_seed_tla_modules.py"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_seed_prover_candidates"] == (
        "python3 scripts/build_ai4fm_public_seed_prover_candidates.py"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_seed_prover_shape_corpora"] == (
        "python3 scripts/build_ai4fm_public_seed_prover_shape_corpora.py"
    )
    assert manifest["remote_next_steps"]["build_ai4fm_public_discovery_manifest"] == (
        "python3 scripts/build_ai4fm_public_discovery_manifest.py"
    )
    assert manifest["remote_next_steps"]["build_sany_tlc_eval_corpus"] == (
        "python3 scripts/build_sany_tlc_eval_corpus.py"
    )
    assert manifest["remote_next_steps"]["inspect_hf_publish_readiness"] == (
        "python3 scripts/inspect_hf_publish_readiness.py"
    )
    assert manifest["remote_next_steps"]["inspect_hf_publish_readiness_fc128best"] == (
        "python3 scripts/inspect_hf_publish_readiness.py "
        "--benchmark-model chattla:20b-fc128best"
    )
    assert "sft_preflight_pbs" not in manifest["remote_next_steps"]
    assert "sft_preflight_launch" not in manifest["remote_next_steps"]
    assert "handoff_status" not in manifest["remote_next_steps"]
    assert "handoff_status_compact" not in manifest["remote_next_steps"]
    assert "handoff_doctor" not in manifest["remote_next_steps"]
    assert "handoff_doctor_compact" not in manifest["remote_next_steps"]
    assert "macmini_known18_handoff" not in manifest["remote_next_steps"]
    assert "macmini_known18_plus_launchagents_handoff" not in manifest["remote_next_steps"]
    assert "macmini_known18_plus_sft_preflight_handoff" not in manifest["remote_next_steps"]
    assert "wait_for_macmini_then_handoff" not in manifest["remote_next_steps"]
    assert "retry_submission_report_mirror" not in manifest["remote_next_steps"]
    assert "install_laptop_wait_handoff_launchagent" not in manifest["remote_next_steps"]
    assert "install_laptop_handoff_doctor_launchagent" not in manifest["remote_next_steps"]
    assert "macmini_launchagents" not in manifest["remote_next_steps"]
