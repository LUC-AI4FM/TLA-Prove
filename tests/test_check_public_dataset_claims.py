import json
from pathlib import Path

from scripts.check_public_dataset_claims import build_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
        json.dumps({"kept_rows": 666, "repo_tla_files": 503, "canonical_clean_tla_files": 205}),
    )
    _write(
        repo / "data/processed/formalllm_public_prover_surface_v1.summary.json",
        json.dumps({"kept_rows": 666, "scanned_formalllm_rows": 410, "repair_candidate_rows": 7}),
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
        json.dumps({"kept_rows": 150}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json",
        json.dumps({"kept_rows": 168, "unique_modules": 114}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json",
        json.dumps({"rows": 18, "kept_rows": 18, "excluded_sany_clean_rows": 150}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_prover_repair_queue_v1.summary.json",
        json.dumps({"kept_rows": 18, "recoverable_without_new_source_rows": 18, "blocked_on_missing_public_dependency_rows": 0}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_prover_recovery_probe_v1.summary.json",
        json.dumps({"kept_rows": 18, "rows_recovered_current_builder": 0, "rows_still_missing_imports_after_staging": 0, "rows_post_stage_non_import_error": 18}),
    )
    _write(
        repo / "outputs/manifests/ai4fm_public_seed_prover_repair_surface.json",
        json.dumps({"repair_surface": {"rows": 18}, "missing_imports": {"rows_with_missing_imports": 18}}),
    )
    _write(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        json.dumps({"total_rows": 1330}),
    )
    _write(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json",
        json.dumps({"total_rows": 2485, "public_import_rows": 1005, "public_seed_candidates_rows": 150}),
    )
    _write(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json",
        json.dumps({"total_rows": 2490, "public_import_rows": 1010, "public_seed_candidates_rows": 150}),
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
                    "tla_files": 410,
                    "clean_tla_files": 205,
                    "nonclean_tla_files": 205,
                },
                "pipeline": {
                    "pull": {"nfiles": 2628},
                    "parse_output": {"nfiles": 3979},
                }
            }
        ),
    )
    _write(repo / "data/processed/ai4fm_public_discovery_manifest_v1.summary.json", json.dumps({"rows": 18}))
    _write(
        repo / "data/processed/benchmark_repair_pairs_fc128best.summary.json",
        json.dumps(
            {
                "rows": 19,
                "failed_rows_seen": 20,
                "gold_coverage": {
                    "covered_failed_rows": 19,
                    "missing_gold_benchmark_ids": ["BM020"],
                },
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
                "blockers": [
                    "latest full benchmark has zero SANY and zero TLC passes; do not publish this model"
                ],
                "failure_surface": {
                    "aggregate": {"rows_with_no_core_components": 20},
                    "red_flags": {"obvious_placeholder_rows": 8},
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
                            "rows": 2485,
                            "matched_distinct_rows": 205,
                            "matched_total_occurrences": 205,
                            "missing_rows": 0,
                            "ok": True,
                        },
                        {
                            "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl",
                            "rows": 2490,
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


def test_build_report_accepts_matching_readme_and_doc_claims(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "ChatTLA currently tracks eight public AI4FM-aligned data/artifact layers spanning the 205-example `FormaLLM` benchmark, a 2,350-row tracked `TLA-Prove` training/eval slice within a 2,757-row committed public JSONL surface, and a 2,110-file / 2,108-module public seed-repo surface:",
                "| `FormaLLM` | 205 canonical prompt/spec entries across 71 families |",
                "| `TLA-Prove public corpora` | 2,350 JSONL rows across the tracked public training/eval corpora; the full committed public JSONL surface currently spans 2,757 rows across 19 files |",
                "| `TLA-Prove normalized import` | 1,005 deduplicated ChatTLA-format rows built from the tracked public corpora slice |",
                "| `TLA-Prove raw import` | 2,350 undeduped ChatTLA-format rows spanning the full tracked public corpora slice |",
                "| `tla-dataset-pipeline seed repo files` | 3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the 11 committed public seed repos, including 2,110 `.tla` files |",
                "| `tla-dataset-pipeline seed prover candidates` | 150 SANY-clean prover-candidate rows from 2,108 usable public seed-module rows |",
                "| `tla-dataset-pipeline discovery` | 18 live public repo records from the checked-in seed/search recipe; 4 of 5 shipped search queries currently return zero repositories |",
                "| `tla-dataset-pipeline` | 2,628 extracted raw files and 3,979 parsed artifacts in the public DVC surface |",
                "The older `1800+` FormaLLM wording comes from a stale architecture-doc note, not the current committed public metadata; ChatTLA treats the live `205`-entry `all_models.json` and `Input/{train,val,test}.json` split files as the canonical public FormaLLM surface.",
                "The verifier-backed preflight manifest at `outputs/manifests/tla_prover_corpus_preflight.json` now proves exact `205/205` `FormaLLM` row coverage across the default, expanded, and full-public prover train corpora rather than relying on summary counts alone.",
                "The current fresh-benchmark repair curriculum for that blocked `fc128best` lane is summarized in `data/processed/benchmark_repair_pairs_fc128best.summary.json`: `19` repair pairs cover `19/20` failed benchmark rows, leaving only `BM020` without a public gold target today.",
                "If someone cites a public AI4FM GitHub surface of `1,800+`, the reproducible interpretation today is the broader expansion lanes above: `2,757` committed `TLA-Prove` JSONL rows, `2,110` public seed `.tla` files, and `2,108` usable seed modules.",
                "Repo-level license provenance across the `11` committed public seed repos is mixed: `3` Apache-2.0, `3` MIT, `2` NOASSERTION, and `3` unknown.",
                "Only the `205`-row `FormaLLM` layer currently feeds `chattla_tla_prover_sft_v1`; the `TLA-Prove` and seed-repo lanes above are audited public expansion artifacts, not yet mixed into that prover corpus.",
                "There is now an explicit non-default expansion build path as well: `data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl` carries the current `1330`-row prover SFT stack plus the `1005`-row normalized public `TLA-Prove` import and `150` public seed prover-candidate replays for `2485` total rows.",
                "The broader committed-public variant is now materialized too: `data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl` carries the same prover stack plus the `1010`-row full-public normalized import for `2490` total rows.",
                "The full tracked-corpora public row lane is also materialized at `data/processed/ai4fm_public_tlaprove_import_raw_v1.jsonl` with `2350` rows when we need the undeduped AI4FM public import surface.",
            ]
        ),
    )
    _write(
        tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md",
        "\n".join(
                [
                    "- `205` canonical metadata entries",
                    "- `410` `.tla` files under `data/*/tla/*.tla`",
                    "- `205` `_clean.tla` files, matching the canonical benchmark row count",
                    "- `205` non-clean `.tla` variants in that same canonical module tree",
                    "- public JSONL rows across the tracked training/eval corpora: `2350`",
                    "- `2350` kept rows in `ai4fm_public_tlaprove_import_raw_v1` when exact-final-spec dedupe is disabled",
                    "- full committed public JSONL surface: `2757` rows across `19` files",
                "- `ai4fm_public_seed_file_manifest_v1.summary.json` reports `2110` public",
                "- `ai4fm_public_seed_tla_modules_v1.summary.json` reports `2108` usable",
                "- `6` repos with clearly permissive SPDX labels at the repo level, versus `5` redistribution-caution repos",
                "- `2350` raw public rows across the tracked corpora",
                "- `1005` kept ChatTLA-format rows after normalization and exact final-spec dedupe",
                "- if someone cites `1800+` for the current public AI4FM GitHub surface, the closest reproducible interpretations today are the broader expansion lanes: `2757` committed `TLA-Prove` JSONL rows, `2110` public seed `.tla` files, or `2108` usable seed modules",
            ]
        ),
    )
    _write(
        tmp_path / "docs/AI4FM_PUBLIC_SURFACE_2026_06_29_LIVE_VERIFICATION.md",
        "\n".join(
            [
                "- `FormaLLM` remains the canonical `205`-entry benchmark layer.",
                "- tracked public training/eval surface: `2350` rows across `6` files",
                "- full committed public JSONL surface: `2757` rows across `19` files",
                "- `2110` public `.tla` files",
                "- `2108` usable module rows",
                "- `4` of the `5` shipped search queries still return zero repositories",
            ]
        ),
    )
    _write(
        tmp_path / "docs/TLA_PROVER_2026_06_29_PUBLIC_CORPUS_NEXT_MOVE_STRATEGY.md",
        "\n".join(
            [
                "| `data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json` | Current default prover SFT is `1330` rows and already includes the full `205`-row `FormaLLM` layer. |",
                "| `data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json` | Non-default tracked-public expanded lane is `2485` rows: `1330` base stack + `1005` normalized public import + `150` SANY-clean seed candidates. |",
                "| `data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json` | Broader committed-public lane is `2490` rows with `1010` normalized public-import rows. |",
                "| `outputs/manifests/ai4fm_public_seed_prover_funnel.json` | `2108` usable seed modules -> `168` shape-ready rows -> `150` SANY-clean rows, leaving `18` shape-ready-but-not-SANY-clean rows. |",
                "The public corpus side is now sufficiently built out. The next real win is to",
                "use the repo's new public lanes to run disciplined, bounded comparisons while",
                "keeping the publish gate strict.",
                "| `outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json` | `chattla:20b-fc128best` has a fresh full benchmark but still `0` SANY / `0` TLC. | Freshness alone does not clear the gate; candidate quality is also non-deployable. |",
            ]
        ),
    )
    _write(
        tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md",
        "\n".join(
            [
                "This bundle ships prover corpora plus metadata summaries for the broader public AI4FM expansion lanes.",
                "- `metadata/ai4fm_org_surface.json`: live public GitHub org snapshot (`8` repos,\n  `3` corpus-relevant).",
                "- `metadata/formalllm_eval_v1.summary.json`: full `FormaLLM` canonical prompt/spec",
                "  layer (`205` rows).",
                "- `metadata/tla_prover_corpus_preflight.json`: schema preflight plus exact `205/205` `FormaLLM` row",
                "  coverage verification across the `1330`-row default, `2485`-row expanded, and",
                "  `2490`-row full-public prover train corpora.",
                "- `metadata/ai4fm_public_tlaprove_corpora.json`: public AI4FM TLA-Prove corpus",
                "  report (`2350` tracked training/eval rows within a `2757`-row committed public",
                "  JSONL surface).",
                "- `metadata/ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json`: raw",
                "  full-public import summary (`2757` undeduped rows).",
                "- `metadata/ai4fm_public_tlaprove_import_all_public_v1.summary.json`: normalized",
                "  full-public import layer (`1010` rows).",
                "- `metadata/ai4fm_public_tlaprove_import_raw_v1.summary.json`: raw tracked-corpora",
                "  import summary (`2350` undeduped rows).",
                "- `metadata/ai4fm_public_seed_file_manifest_v1.summary.json`: public GitHub seed",
                "  file manifest (`3140` tracked files, `2110` `.tla` files, `2108` usable module rows).",
                "- `metadata/ai4fm_public_seed_tla_modules_v1.summary.json`: usable public `.tla`",
                "  module corpus (`2108` rows).",
                "- `metadata/ai4fm_public_seed_license_surface.json`: repo-level SPDX/provenance",
                "  rollup for the `11` committed public seed repos.",
                "- `metadata/hf_publish_readiness.json`: canonical publish-readiness gate (`2`",
                "  blockers; `20` latest benchmark rows still missing every core TLA component).",
                "- `metadata/hf_publish_readiness.chattla_20b_fc128best.json`: fresh `fc128best`",
                "  publish-readiness gate (`1` blocker; `20` rows still missing every core component,",
                "  `8` with obvious placeholder text).",
                "- `metadata/benchmark_repair_pairs_fc128best.summary.json`: benchmark-derived",
                "  repair curriculum summary (`19` rows covering `19` of `20` failed fresh-benchmark",
                "  cases; `1` missing gold target).",
                "- Mixed prover SFT corpus: `1330` rows",
                "- `metadata/chattla_tla_prover_sft_public_expanded_v1.summary.json`: non-default\n  public-AI4FM expanded prover SFT summary (`2485` rows total; `1005` normalized import rows + `150` seed prover-candidate replays on top of the baseline prover stack).",
                "- `metadata/chattla_tla_prover_sft_public_all_v1.summary.json`: full-public\n  expanded prover SFT summary (`2490` rows total; `1010` normalized full-public import rows on top of the baseline prover stack).",
                "- `metadata/tla_prover_corpus_experiment_matrix.json`: bounded corpus-lane\n  comparison matrix covering the `1330`-row baseline, `2485`-row expanded lane,\n  `2490`-row full-public lane, and the `150`/`2108` public seed funnel.",
                "- Public AI4FM normalized import: `1005` rows from the tracked `2350`-row",
                "  public corpora slice.",
                "- Public seed repo license surface: `3` Apache-2.0 repos, `3` MIT repos, `2`",
                "  NOASSERTION repos, and `3` unknown-license repos.",
                "- Public AI4FM seed-module prover candidates: `150` rows out of `2108` usable",
                "  public seed-module rows.",
                "- Canonical publish readiness gate: blocked, with `20` of `20` latest benchmark rows",
                "  missing every core TLA component.",
                "- `fc128best` publish readiness gate: blocked, with `20` of `20` rows missing every core component",
                "  and `8` obvious-placeholder failures.",
                "- Benchmark-derived repair curriculum: `19` rows covering `19` of `20`",
                "  failed fresh-benchmark cases, with `1` missing gold target.",
                "The AI4FM import and seed-repo lanes are metadata-only audit surfaces in this bundle; they are not yet mixed into `data/train/chattla_tla_prover_sft_v1.jsonl`.",
            ]
        ),
    )

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
                "ChatTLA currently tracks seven public AI4FM-aligned data/artifact layers spanning the 205-example `FormaLLM` benchmark, a 2,350-row tracked `TLA-Prove` training/eval slice within a 2,757-row committed public JSONL surface, and a 2,110-file / 2,108-module public seed-repo surface:",
                "| `FormaLLM` | 205 canonical prompt/spec entries across 71 families |",
                "| `TLA-Prove public corpora` | 2,350 JSONL rows across the tracked public training/eval corpora; the full committed public JSONL surface currently spans 2,757 rows across 19 files |",
                "| `TLA-Prove normalized import` | 1,005 deduplicated ChatTLA-format rows built from the tracked public corpora slice |",
                "| `TLA-Prove raw import` | 2,350 undeduped ChatTLA-format rows spanning the full tracked public corpora slice |",
                "| `tla-dataset-pipeline seed repo files` | 3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the 11 committed public seed repos, including 2,110 `.tla` files |",
                "| `tla-dataset-pipeline seed prover candidates` | 150 SANY-clean prover-candidate rows from 2,108 usable public seed-module rows |",
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
