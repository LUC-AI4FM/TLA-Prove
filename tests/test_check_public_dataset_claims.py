import json
from pathlib import Path

from scripts.check_public_dataset_claims import build_report

REPO = Path(__file__).resolve().parents[1]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    _write(path, "".join(json.dumps(row) + "\n" for row in rows))


def _write_bundle_copy(repo: Path, bundle_name: str, source_rel: str) -> None:
    source = repo / source_rel
    _write(
        repo / "outputs/hf_publish/chattla-tla-prover-corpora-v1/metadata" / bundle_name,
        source.read_text(encoding="utf-8"),
    )


def _write_manifests(repo: Path) -> None:
    _write(
        repo / "data/processed/formalllm_eval_v1.summary.json",
        json.dumps({"rows": 205, "families_seen": 71}),
    )
    _write(
        repo / "data/processed/formalllm_public_module_manifest_v1.summary.json",
        json.dumps(
            {
                "kept_rows": 666,
                "repo_tla_files": 503,
                "repo_cfg_files": 163,
                "canonical_tree_tla_files": 410,
                "canonical_clean_tla_files": 205,
            }
        ),
    )
    _write(
        repo / "data/processed/formalllm_public_prover_surface_v1.summary.json",
        json.dumps(
            {
                "kept_rows": 666,
                "scanned_formalllm_rows": 410,
                "repair_candidate_rows": 7,
                "status_counts": {"skipped": 403, "tlc_error": 7},
            }
        ),
    )
    _write(
        repo / "data/processed/tlapm_public_tla_modules_v1.summary.json",
        json.dumps({"kept_rows": 14, "repo_head_sha": "80172c61842c8dd15524c6f01a70ba91029802f5"}),
    )
    _write(
        repo / "outputs/manifests/ai4fm_public_tlaprove_corpora.json",
        json.dumps(
            {
                "aggregate": {
                    "total_public_jsonl_rows": 2350,
                    "all_public_jsonl_rows": 2757,
                    "all_public_jsonl_files": 19,
                    "tracked_public_jsonl_files": 6,
                    "largest_public_jsonl": {
                        "path": "data/processed/diamond_sft_v3.jsonl",
                        "rows": 1053,
                    },
                }
            }
        ),
    )
    _write(
        repo / "data/processed/ai4fm_public_tlaprove_import_v1.summary.json",
        json.dumps({"kept_rows": 1005}),
    )
    _write(
        repo / "data/processed/ai4fm_public_tlaprove_import_all_public_v1.summary.json",
        json.dumps({"kept_rows": 1010}),
    )
    _write(
        repo / "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json",
        json.dumps({"kept_rows": 2350}),
    )
    _write(
        repo / "data/processed/ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json",
        json.dumps({"kept_rows": 2757}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json",
        json.dumps({"seed_repo_inputs": 11, "kept_rows": 3140, "totals": {"all": 3140, "tla": 2110}}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json",
        json.dumps({"kept_rows": 2108}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_prover_candidates_v1.summary.json",
        json.dumps({"kept_rows": 168}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json",
        json.dumps({"kept_rows": 168, "unique_modules": 114}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json",
        json.dumps({"rows": 0, "kept_rows": 0, "excluded_sany_clean_rows": 168}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_prover_repair_queue_v1.summary.json",
        json.dumps({"kept_rows": 0, "recoverable_without_new_source_rows": 0, "blocked_on_missing_public_dependency_rows": 0}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_prover_recovery_probe_v1.summary.json",
        json.dumps({"kept_rows": 0, "rows_recovered_current_builder": 0, "rows_still_missing_imports_after_staging": 0, "rows_post_stage_non_import_error": 0}),
    )
    _write(
        repo / "outputs/manifests/ai4fm_public_seed_prover_repair_surface.json",
        json.dumps({"repair_surface": {"rows": 0}, "missing_imports": {"rows_with_missing_imports": 0}}),
    )
    _write(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        json.dumps({"total_rows": 1330}),
    )
    _write(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json",
        json.dumps({"total_rows": 2503, "public_import_rows": 1005, "public_seed_candidates_rows": 168}),
    )
    _write(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json",
        json.dumps({"total_rows": 2508, "public_import_rows": 1010, "public_seed_candidates_rows": 168}),
    )
    _write(
        repo / "outputs/manifests/ai4fm_org_surface.json",
        json.dumps({"public_repo_count": 8, "summary": {"corpus_relevant_repo_count": 3}}),
    )
    _write(
        repo / "outputs/manifests/ai4fm_public_seed_license_surface.json",
        json.dumps(
            {
                "license_summary": {
                    "repo_counts": {
                        "Apache-2.0": 3,
                        "MIT": 3,
                        "NOASSERTION": 2,
                        "UNKNOWN": 3,
                    },
                    "clearly_permissive_repo_count": 6,
                    "caution_repo_count": 5,
                }
            }
        ),
    )
    _write(
        repo / "outputs/manifests/ai4fm_public_dataset_surface.json",
        json.dumps(
            {
                "formalllm": {
                    "canonical_entries": 205,
                    "tla_files": 410,
                    "clean_tla_files": 205,
                    "nonclean_tla_files": 205,
                    "split_files": {"total": 205},
                },
                "pipeline": {
                    "pull": {"nfiles": 2628},
                    "parse_output": {"nfiles": 3979},
                }
                ,
                "broader_public_lanes": {
                    "tla_prove_committed_public_jsonl": {"rows": 2757},
                    "seed_repo_tla_files": {"rows": 2110},
                    "usable_seed_modules": {"rows": 2108},
                    "sany_clean_seed_prover_candidates": {"rows": 168},
                    "shape_ready_seed_rows": {"rows": 168},
                    "shape_ready_not_sany_rows": {"rows": 0},
                },
            }
        ),
    )
    _write(repo / "data/processed/ai4fm_public_discovery_manifest_v1.summary.json", json.dumps({"rows": 18}))
    _write(
        repo / "data/processed/benchmark_repair_pairs_fc128best.summary.json",
        json.dumps(
            {
                "rows": 20,
                "failed_rows_seen": 20,
                "gold_coverage": {"covered_failed_rows": 20, "missing_gold_benchmark_ids": []},
                "public_module_fallback_benchmark_ids": ["BM020"],
            }
        ),
    )
    _write(
        repo / "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.summary.json",
        json.dumps(
            {
                "rows": 22,
                "candidate_rows": 37,
                "validated_tier_counts": {"gold": 18, "silver": 5, "bronze": 6},
                "kept_by_bucket": {"proof_repair": 15, "inductiveness_repair": 3, "tlc_repair": 4},
            }
        ),
    )
    _write(
        repo / "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.summary.json",
        json.dumps(
            {
                "rows": 8,
                "candidate_rows": 8,
                "validated_tier_counts": {"gold": 4, "silver": 4},
                "kept_by_bucket": {"skip_harness_repair": 8},
                "only_buckets": ["skip_harness_repair"],
            }
        ),
    )
    _write(
        repo / "data/processed/tla_prover_repair_train_v1.summary.json",
        json.dumps(
            {
                "rows": 541,
                "kept_rows_by_source": {
                    "data/processed/benchmark_repair_pairs_fc128best.jsonl": 20,
                    "data/processed/tla_prover_synthetic_repair_pairs_v1.jsonl": 491,
                    "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.jsonl": 22,
                    "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.jsonl": 8,
                },
                "difficulty_counts": {"easy": 256, "medium": 61, "hard": 224},
                "health": {"ok": True, "benchmark_only": False, "only_easy_rows": False, "warnings": []},
            }
        ),
    )
    _write(repo / "data/processed/prover_eval.summary.json", json.dumps({"kept_rows": 18}))
    _write(
        repo / "outputs/manifests/hf_publish_readiness.json",
        json.dumps(
            {
                "blockers": [
                    "latest full benchmark is stale at 1405.2h (limit 24.0h)",
                    "latest full benchmark has zero SANY and zero TLC passes; do not publish this model",
                ],
                "failure_surface": {
                    "aggregate": {"rows_with_no_core_components": 20},
                    "red_flags": {"obvious_placeholder_rows": 0},
                },
            }
        ),
    )
    _write(
        repo / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        json.dumps(
            {
                "blockers": [],
                "failure_surface": {
                    "rows": 20,
                    "aggregate": {"rows_with_no_core_components": 14},
                    "red_flags": {"obvious_placeholder_rows": 1},
                },
            }
        ),
    )
    _write(repo / "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json", json.dumps({"ok": True}))
    _write(repo / "data/processed/sany_tlc_pass_eval_v1.summary.json", json.dumps({"kept_rows": 30}))
    _write(repo / "data/processed/sany_tlc_pass_sft_v1.summary.json", json.dumps({"kept_rows": 170}))
    _write(repo / "outputs/manifests/tla_prover_artifacts_v1.json", json.dumps({"schema": "artifact"}))
    _write(
        repo / "outputs/manifests/tla_prover_corpus_preflight.json",
        json.dumps(
            {
                "ok": True,
                "formalllm_coverage": {
                    "ok": True,
                    "formalllm_rows": 205,
                    "corpora": [
                        {
                            "path": "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
                            "rows": 1330,
                            "matched_distinct_rows": 205,
                            "matched_total_occurrences": 205,
                            "missing_rows": 0,
                            "ok": True,
                        },
                        {
                            "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
                            "rows": 2503,
                            "matched_distinct_rows": 205,
                            "matched_total_occurrences": 205,
                            "missing_rows": 0,
                            "ok": True,
                        },
                        {
                            "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl",
                            "rows": 2508,
                            "matched_distinct_rows": 205,
                            "matched_total_occurrences": 205,
                            "missing_rows": 0,
                            "ok": True,
                        },
                    ],
                },
            }
        ),
    )
    _write(
        repo / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        json.dumps({"schema": "chattla_tla_prover_corpus_experiment_matrix_v1"}),
    )
    _write(
        repo / "outputs/manifests/tla_prover_full_dataset_failure_analysis.json",
        json.dumps({"rows": 610, "action_bucket_counts": {"proof_repair": 79}}),
    )
    _write(
        repo / "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json",
        json.dumps({"rows": 18}),
    )
    _write(
        repo / "outputs/hf_publish/chattla-tla-prover-corpora-v1/metadata/sany_tlc_pass_eval_replay.json",
        json.dumps({"rows": 30}),
    )

    for bundle_name, source_rel in {
        "ai4fm_org_surface.json": "outputs/manifests/ai4fm_org_surface.json",
        "ai4fm_public_dataset_surface.json": "outputs/manifests/ai4fm_public_dataset_surface.json",
        "ai4fm_public_discovery_manifest_v1.summary.json": "data/processed/ai4fm_public_discovery_manifest_v1.summary.json",
        "benchmark_repair_pairs_fc128best.summary.json": "data/processed/benchmark_repair_pairs_fc128best.summary.json",
        "tla_prover_repair_train_v1.summary.json": "data/processed/tla_prover_repair_train_v1.summary.json",
        "tla_prover_full_dataset_validated_repair_pairs_v1.summary.json": "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.summary.json",
        "tla_prover_full_dataset_harness_repair_pairs_v1.summary.json": "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.summary.json",
        "formalllm_public_module_manifest_v1.summary.json": "data/processed/formalllm_public_module_manifest_v1.summary.json",
        "formalllm_public_prover_surface_v1.summary.json": "data/processed/formalllm_public_prover_surface_v1.summary.json",
        "tlapm_public_tla_modules_v1.summary.json": "data/processed/tlapm_public_tla_modules_v1.summary.json",
        "ai4fm_public_seed_file_manifest_v1.summary.json": "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json",
        "ai4fm_public_seed_license_surface.json": "outputs/manifests/ai4fm_public_seed_license_surface.json",
        "ai4fm_public_seed_tla_modules_v1.summary.json": "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json",
        "ai4fm_public_seed_prover_candidates_v1.summary.json": "data/processed/ai4fm_public_seed_prover_candidates_v1.summary.json",
        "ai4fm_public_seed_prover_shape_ready_v1.summary.json": "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json",
        "ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json": "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json",
        "ai4fm_public_seed_prover_repair_queue_v1.summary.json": "data/processed/ai4fm_public_seed_prover_repair_queue_v1.summary.json",
        "ai4fm_public_seed_prover_recovery_probe_v1.summary.json": "data/processed/ai4fm_public_seed_prover_recovery_probe_v1.summary.json",
        "ai4fm_public_seed_prover_repair_surface.json": "outputs/manifests/ai4fm_public_seed_prover_repair_surface.json",
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
        _write_bundle_copy(repo, bundle_name, source_rel)


def _write_bundle_data_copies(repo: Path) -> None:
    pairs = {
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl": "data/train/chattla_tla_prover_sft_v1.jsonl",
        "data/processed/sany_tlc_pass_sft_v1.jsonl": "data/train/sany_tlc_pass_sft_v1.jsonl",
        "data/processed/prover_eval.jsonl": "data/eval/prover_eval.jsonl",
        "data/processed/sany_tlc_pass_eval_v1.jsonl": "data/eval/sany_tlc_pass_eval_v1.jsonl",
        "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl": (
            "data/traces/tlaps_verified_autoprover_traces_v1.jsonl"
        ),
    }
    rows = [{"messages": [{"role": "assistant", "channel": "final", "content": "ok"}]}]
    for source_rel, bundle_rel in pairs.items():
        _write_jsonl(repo / source_rel, rows)
        _write_jsonl(repo / "outputs/hf_publish/chattla-tla-prover-corpora-v1" / bundle_rel, rows)


def test_build_report_accepts_matching_readme_and_doc_claims(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write_bundle_data_copies(tmp_path)
    _write(tmp_path / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    for rel_path in (
        "docs/AI4FM_PUBLIC_DATASET_SURFACE.md",
        "docs/AI4FM_PUBLIC_SURFACE_2026_06_29_LIVE_VERIFICATION.md",
        "docs/TLA_PROVER_2026_06_29_PUBLIC_CORPUS_NEXT_MOVE_STRATEGY.md",
        "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md",
    ):
        _write(tmp_path / rel_path, (REPO / rel_path).read_text(encoding="utf-8"))

    report = build_report(repo=tmp_path)

    assert report["ok"] is True
    assert report["findings"] == []


def test_build_report_flags_mismatched_public_claims(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(tmp_path / "README.md", "FormaLLM benchmark has 204 rows.\n")
    _write(tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md", "public JSONL rows across the tracked training/eval corpora: `9999`\n")

    report = build_report(repo=tmp_path)

    assert report["ok"] is False
    assert any("205 canonical prompt/spec entries across 71 families" in finding["expected"] for finding in report["findings"])
    assert any("public JSONL rows across the tracked training/eval corpora: `2350`" in finding["expected"] for finding in report["findings"])


def test_build_report_flags_public_dataset_layer_count_mismatch(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "ChatTLA currently tracks seven public AI4FM-aligned data/artifact layers spanning the 205-example `FormaLLM` benchmark, the broader 666-record checked-in `FormaLLM` repo surface, a 2,350-row tracked `TLA-Prove` training/eval slice within a 2,757-row committed public JSONL surface, and a 2,110-file / 2,108-module public seed-repo surface:",
                "| `FormaLLM` | 205 canonical prompt/spec entries across 71 families |",
                "| `FormaLLM public repo file surface` | 666 tracked public file records spanning 503 `.tla` files, 163 `.cfg` files, and the full 410-file canonical module tree |",
                "| `FormaLLM prover-facing smoke surface` | 410 canonical `.tla` rows joined against the latest full-dataset smoke; 7 current TLC repair candidates and 403 skipped rows in the broader canonical tree replay |",
                "| `TLA-Prove public corpora` | 2,350 JSONL rows across the tracked public training/eval corpora; the full committed public JSONL surface currently spans 2,757 rows across 19 files |",
                "| `TLA-Prove normalized import` | 1,005 deduplicated ChatTLA-format rows built from the tracked public corpora slice |",
                "| `TLA-Prove raw import` | 2,350 undeduped ChatTLA-format rows spanning the full tracked public corpora slice |",
                "| `tla-dataset-pipeline seed repo files` | 3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the 11 committed public seed repos, including 2,110 `.tla` files |",
                "| `tla-dataset-pipeline seed prover candidates` | 168 SANY-clean prover-candidate rows from 2,108 usable public seed-module rows |",
                "| `tla-dataset-pipeline discovery` | 18 live public repo records from the checked-in seed/search recipe; 4 of 5 shipped search queries currently return zero repositories |",
                "| `tla-dataset-pipeline` | 2,628 extracted raw files and 3,979 parsed artifacts in the public DVC surface |",
            ]
        ),
    )
    _write(tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md", "")
    _write(tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md", "")

    report = build_report(repo=tmp_path)

    assert report["ok"] is False
    assert any(
        "public AI4FM dataset intro count to match the number of dataset table rows" in finding["expected"]
        for finding in report["findings"]
    )


def test_build_report_flags_missing_or_stale_hf_bundle_metadata(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(tmp_path / "README.md", "")
    _write(tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md", "")
    _write(tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md", "")

    missing = tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/metadata/ai4fm_public_seed_license_surface.json"
    missing.unlink()
    _write(
        tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/metadata/tla_prover_artifacts_v1.json",
        "{\"schema\":\"stale\"}",
    )

    report = build_report(repo=tmp_path)

    assert report["ok"] is False
    assert any(
        finding["path"] == "outputs/hf_publish/chattla-tla-prover-corpora-v1/metadata/ai4fm_public_seed_license_surface.json"
        and "bundled copy of outputs/manifests/ai4fm_public_seed_license_surface.json" in finding["expected"]
        for finding in report["findings"]
    )
    assert any(
        finding["path"] == "outputs/hf_publish/chattla-tla-prover-corpora-v1/metadata/tla_prover_artifacts_v1.json"
        and "exact content match for outputs/manifests/tla_prover_artifacts_v1.json" in finding["expected"]
        for finding in report["findings"]
    )


def test_build_report_flags_stale_ai4fm_public_dataset_surface_counts(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(tmp_path / "README.md", "")
    _write(tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md", "")
    _write(tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md", "")
    _write(
        tmp_path / "outputs/manifests/ai4fm_public_dataset_surface.json",
        json.dumps(
            {
                "formalllm": {
                    "canonical_entries": 204,
                    "tla_files": 410,
                    "clean_tla_files": 204,
                    "nonclean_tla_files": 205,
                    "split_files": {"total": 204},
                },
                "pipeline": {
                    "pull": {"nfiles": 2628},
                    "parse_output": {"nfiles": 3979},
                },
                "broader_public_lanes": {
                    "tla_prove_committed_public_jsonl": {"rows": 2757},
                    "seed_repo_tla_files": {"rows": 2110},
                    "usable_seed_modules": {"rows": 2108},
                    "sany_clean_seed_prover_candidates": {"rows": 124},
                    "shape_ready_seed_rows": {"rows": 168},
                    "shape_ready_not_sany_rows": {"rows": 44},
                },
            }
        ),
    )
    _write_bundle_copy(
        tmp_path,
        "ai4fm_public_dataset_surface.json",
        "outputs/manifests/ai4fm_public_dataset_surface.json",
    )

    report = build_report(repo=tmp_path)

    assert report["ok"] is False
    assert any(
        finding["path"] == "outputs/manifests/ai4fm_public_dataset_surface.json"
        and "formalllm.canonical_entries == 205" in finding["expected"]
        for finding in report["findings"]
    )
    assert any(
        finding["path"] == "outputs/manifests/ai4fm_public_dataset_surface.json"
        and "formalllm.clean_tla_files == 205" in finding["expected"]
        for finding in report["findings"]
    )
    assert any(
        finding["path"] == "outputs/manifests/ai4fm_public_dataset_surface.json"
        and "formalllm.split_files.total == 205" in finding["expected"]
        for finding in report["findings"]
    )
    assert any(
        finding["path"] == "outputs/manifests/ai4fm_public_dataset_surface.json"
        and "broader_public_lanes.sany_clean_seed_prover_candidates.rows == 168" in finding["expected"]
        for finding in report["findings"]
    )
    assert any(
        finding["path"] == "outputs/manifests/ai4fm_public_dataset_surface.json"
        and "broader_public_lanes.shape_ready_not_sany_rows.rows == 0" in finding["expected"]
        for finding in report["findings"]
    )


def test_build_report_flags_stale_formalllm_preflight_count(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(tmp_path / "README.md", "")
    _write(tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md", "")
    _write(tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md", "")
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_preflight.json",
        json.dumps(
            {
                "ok": True,
                "formalllm_coverage": {
                    "ok": True,
                    "formalllm_rows": 204,
                    "corpora": [
                        {
                            "path": "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
                            "rows": 1330,
                            "matched_distinct_rows": 205,
                            "matched_total_occurrences": 205,
                            "missing_rows": 0,
                            "ok": True,
                        },
                        {
                            "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
                            "rows": 2503,
                            "matched_distinct_rows": 205,
                            "matched_total_occurrences": 205,
                            "missing_rows": 0,
                            "ok": True,
                        },
                        {
                            "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl",
                            "rows": 2508,
                            "matched_distinct_rows": 205,
                            "matched_total_occurrences": 205,
                            "missing_rows": 0,
                            "ok": True,
                        },
                    ],
                },
            }
        ),
    )
    _write_bundle_copy(
        tmp_path,
        "tla_prover_corpus_preflight.json",
        "outputs/manifests/tla_prover_corpus_preflight.json",
    )

    report = build_report(repo=tmp_path)

    assert report["ok"] is False
    assert any(
        finding["path"] == "outputs/manifests/tla_prover_corpus_preflight.json"
        and "formalllm_coverage.formalllm_rows == 205" in finding["expected"]
        for finding in report["findings"]
    )


def test_build_report_flags_stale_formalllm_canonical_clean_count(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(tmp_path / "README.md", "")
    _write(tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md", "")
    _write(tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md", "")
    _write(
        tmp_path / "data/processed/formalllm_public_module_manifest_v1.summary.json",
        json.dumps(
            {
                "kept_rows": 666,
                "repo_tla_files": 503,
                "repo_cfg_files": 163,
                "canonical_tree_tla_files": 410,
                "canonical_clean_tla_files": 204,
            }
        ),
    )
    _write_bundle_copy(
        tmp_path,
        "formalllm_public_module_manifest_v1.summary.json",
        "data/processed/formalllm_public_module_manifest_v1.summary.json",
    )

    report = build_report(repo=tmp_path)

    assert report["ok"] is False
    assert any(
        finding["path"] == "data/processed/formalllm_public_module_manifest_v1.summary.json"
        and "canonical_clean_tla_files == 205" in finding["expected"]
        for finding in report["findings"]
    )


def test_build_report_flags_stale_public_corpus_doc_counts(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(tmp_path / "README.md", "")
    _write(tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md", "")
    _write(
        tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md",
        "\n".join(
            [
                "- `98` `ai4fm_public_seed_prover_candidates_v1` rows are ChatTLA-derived downstream corpora",
                "- `2490` total rows (`1330` baseline prover stack + `1010` full-public normalized import + `150` seed prover-candidate replays)",
                "  exposing a `2485`-row public-AI4FM expansion lane (`1330` default prover SFT rows + `1005` normalized public import rows + `150` public seed prover-candidate replays).",
            ]
        ),
    )
    _write(
        tmp_path / "docs/AI4FM_PUBLIC_SURFACE_2026_06_29_LIVE_VERIFICATION.md",
        "\n".join(
            [
                "- treat data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl as a non-default `2490`-row experiment lane for the broader committed-public AI4FM surface;",
                "2. run verifier-backed experiments on the `2490`-row full-public lane before changing any default training path;",
            ]
        ),
    )

    report = build_report(repo=tmp_path)

    assert report["ok"] is False
    assert any(
        finding["path"] == "docs/AI4FM_PUBLIC_DATASET_SURFACE.md"
        and "`1005` normalized `ai4fm_public_tlaprove_import_v1` rows and `168`" in finding["expected"]
        for finding in report["findings"]
    )
    assert any(
        finding["path"] == "docs/AI4FM_PUBLIC_DATASET_SURFACE.md"
        and "normalized import + `168` seed prover-candidate replays)" in finding["expected"]
        for finding in report["findings"]
    )
    assert any(
        finding["path"] == "docs/AI4FM_PUBLIC_SURFACE_2026_06_29_LIVE_VERIFICATION.md"
        and "non-default `2508`-row experiment lane" in finding["expected"]
        for finding in report["findings"]
    )


def test_build_report_flags_public_bundle_jsonl_leaks(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(tmp_path / "README.md", "")
    _write(tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md", "")
    _write(tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md", "")
    _write(tmp_path / "docs/AI4FM_PUBLIC_SURFACE_2026_06_29_LIVE_VERIFICATION.md", "")

    for source_rel in {
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
        "data/processed/prover_eval.jsonl",
        "data/processed/sany_tlc_pass_sft_v1.jsonl",
        "data/processed/sany_tlc_pass_eval_v1.jsonl",
        "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl",
    }:
        _write_jsonl(tmp_path / source_rel, [{"messages": [{"role": "assistant", "channel": "final", "content": "ok"}]}])

    for bundle_rel in {
        "data/train/chattla_tla_prover_sft_v1.jsonl",
        "data/train/sany_tlc_pass_sft_v1.jsonl",
        "data/eval/prover_eval.jsonl",
        "data/eval/sany_tlc_pass_eval_v1.jsonl",
        "data/traces/tlaps_verified_autoprover_traces_v1.jsonl",
    }:
        rows = [{"messages": [{"role": "assistant", "channel": "final", "content": "ok"}]}]
        if bundle_rel.endswith("chattla_tla_prover_sft_v1.jsonl"):
            rows = [
                {
                    "messages": [
                        {"role": "user", "content": "contact alice@example.com"},
                        {"role": "assistant", "channel": "analysis", "content": "internal"},
                        {"role": "assistant", "channel": "final", "content": "ok"},
                    ]
                }
            ]
        _write_jsonl(tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1" / bundle_rel, rows)

    report = build_report(repo=tmp_path)

    assert report["ok"] is False
    assert any(
        finding["path"] == "outputs/hf_publish/chattla-tla-prover-corpora-v1/data/train/chattla_tla_prover_sft_v1.jsonl"
        and "scrub public email addresses" in finding["expected"]
        for finding in report["findings"]
    )
