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
        json.dumps({"kept_rows": 98}),
    )
    _write(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        json.dumps({"total_rows": 1330}),
    )
    _write(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json",
        json.dumps({"total_rows": 2433, "public_import_rows": 1005, "public_seed_candidates_rows": 98}),
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
                "pipeline": {
                    "pull": {"nfiles": 2628},
                    "parse_output": {"nfiles": 3979},
                }
            }
        ),
    )
    _write(repo / "data/processed/ai4fm_public_discovery_manifest_v1.summary.json", json.dumps({"rows": 18}))
    _write(repo / "data/processed/prover_eval.summary.json", json.dumps({"kept_rows": 18}))
    _write(repo / "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json", json.dumps({"ok": True}))
    _write(repo / "data/processed/sany_tlc_pass_eval_v1.summary.json", json.dumps({"kept_rows": 30}))
    _write(repo / "data/processed/sany_tlc_pass_sft_v1.summary.json", json.dumps({"kept_rows": 170}))
    _write(repo / "outputs/manifests/tla_prover_artifacts_v1.json", json.dumps({"schema": "artifact"}))
    _write(repo / "outputs/manifests/tla_prover_corpus_preflight.json", json.dumps({"ok": True}))
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
        "ai4fm_public_seed_file_manifest_v1.summary.json": "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json",
        "ai4fm_public_seed_license_surface.json": "outputs/manifests/ai4fm_public_seed_license_surface.json",
        "ai4fm_public_seed_tla_modules_v1.summary.json": "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json",
        "ai4fm_public_seed_prover_candidates_v1.summary.json": "data/processed/ai4fm_public_seed_prover_candidates_v1.summary.json",
        "ai4fm_public_tlaprove_corpora.json": "outputs/manifests/ai4fm_public_tlaprove_corpora.json",
        "ai4fm_public_tlaprove_import_all_public_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_all_public_v1.summary.json",
        "ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json",
        "ai4fm_public_tlaprove_import_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_v1.summary.json",
        "ai4fm_public_tlaprove_import_raw_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json",
        "chattla_tla_prover_sft_public_expanded_v1.summary.json": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json",
        "chattla_tla_prover_sft_v1.summary.json": "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        "formalllm_eval_v1.summary.json": "data/processed/formalllm_eval_v1.summary.json",
        "prover_eval.summary.json": "data/processed/prover_eval.summary.json",
        "sany_tlc_pass_corpus_diagnostic.json": "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json",
        "sany_tlc_pass_eval_v1.summary.json": "data/processed/sany_tlc_pass_eval_v1.summary.json",
        "sany_tlc_pass_sft_v1.summary.json": "data/processed/sany_tlc_pass_sft_v1.summary.json",
        "tla_prover_artifacts_v1.json": "outputs/manifests/tla_prover_artifacts_v1.json",
        "tla_prover_corpus_preflight.json": "outputs/manifests/tla_prover_corpus_preflight.json",
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
                "| `TLA-Prove normalized import` | 1,005 deduplicated ChatTLA-format rows built from the committed public corpora |",
                "| `TLA-Prove raw import` | 2,350 undeduped ChatTLA-format rows spanning the full tracked public corpora slice |",
                "| `tla-dataset-pipeline seed repo files` | 3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the 11 committed public seed repos, including 2,110 `.tla` files |",
                "| `tla-dataset-pipeline seed prover candidates` | 98 SANY-clean prover-candidate rows from 2,108 usable public seed-module rows |",
                "| `tla-dataset-pipeline discovery` | 18 live public repo records from the checked-in seed/search recipe; 4 of 5 shipped search queries currently return zero repositories |",
                "| `tla-dataset-pipeline` | 2,628 extracted raw files and 3,979 parsed artifacts in the public DVC surface |",
                "The older `1800+` FormaLLM wording comes from a stale architecture-doc note, not the current committed public metadata; ChatTLA treats the live `205`-entry `all_models.json` and `Input/{train,val,test}.json` split files as the canonical public FormaLLM surface.",
                "If someone cites a public AI4FM GitHub surface of `1,800+`, the reproducible interpretation today is the broader expansion lanes above: `2,757` committed `TLA-Prove` JSONL rows, `2,110` public seed `.tla` files, and `2,108` usable seed modules.",
                "Repo-level license provenance across the `11` committed public seed repos is mixed: `3` Apache-2.0, `3` MIT, `2` NOASSERTION, and `3` unknown.",
                "Only the `205`-row `FormaLLM` layer currently feeds `chattla_tla_prover_sft_v1`; the `TLA-Prove` and seed-repo lanes above are audited public expansion artifacts, not yet mixed into that prover corpus.",
                "There is now an explicit non-default expansion build path as well: `data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl` carries the current `1330`-row prover SFT stack plus the `1005`-row normalized public `TLA-Prove` import and `98` public seed prover-candidate replays for `2433` total rows.",
                "The full tracked-corpora public row lane is also materialized at `data/processed/ai4fm_public_tlaprove_import_raw_v1.jsonl` with `2350` rows when we need the undeduped AI4FM public import surface.",
            ]
        ),
    )
    _write(
        tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md",
        "\n".join(
            [
                "- `205` canonical metadata entries",
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
        tmp_path / "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md",
        "\n".join(
            [
                "This bundle ships prover corpora plus metadata summaries for the broader public AI4FM expansion lanes.",
                "- `metadata/ai4fm_org_surface.json`: live public GitHub org snapshot (`8` repos,\n  `3` corpus-relevant).",
                "- `metadata/formalllm_eval_v1.summary.json`: full `FormaLLM` canonical prompt/spec",
                "  layer (`205` rows).",
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
                "- Mixed prover SFT corpus: `1330` rows",
                "- `metadata/chattla_tla_prover_sft_public_expanded_v1.summary.json`: non-default\n  public-AI4FM expanded prover SFT summary (`2433` rows total; `1005` normalized import rows + `98` seed prover-candidate replays on top of the baseline prover stack).",
                "- Public AI4FM normalized import: `1005` rows from the tracked `2350`-row",
                "  public corpora slice.",
                "- Public seed repo license surface: `3` Apache-2.0 repos, `3` MIT repos, `2`",
                "  NOASSERTION repos, and `3` unknown-license repos.",
                "- Public AI4FM seed-module prover candidates: `98` rows out of `2108` usable",
                "  public seed-module rows.",
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
                "| `TLA-Prove normalized import` | 1,005 deduplicated ChatTLA-format rows built from the committed public corpora |",
                "| `TLA-Prove raw import` | 2,350 undeduped ChatTLA-format rows spanning the full tracked public corpora slice |",
                "| `tla-dataset-pipeline seed repo files` | 3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the 11 committed public seed repos, including 2,110 `.tla` files |",
                "| `tla-dataset-pipeline seed prover candidates` | 98 SANY-clean prover-candidate rows from 2,108 usable public seed-module rows |",
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
