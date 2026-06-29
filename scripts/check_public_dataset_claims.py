#!/usr/bin/env python3
"""Validate that public dataset claims in README/docs match tracked manifests."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = REPO / "outputs" / "hf_publish" / "chattla-tla-prover-corpora-v1"
BUNDLE_METADATA = BUNDLE_ROOT / "metadata"
COUNT_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _comma(value: int) -> str:
    return f"{value:,}"


def _bundled_metadata_sources(repo: Path) -> dict[str, str]:
    return {
        "ai4fm_org_surface.json": "outputs/manifests/ai4fm_org_surface.json",
        "ai4fm_public_dataset_surface.json": "outputs/manifests/ai4fm_public_dataset_surface.json",
        "ai4fm_public_discovery_manifest_v1.summary.json": "data/processed/ai4fm_public_discovery_manifest_v1.summary.json",
        "benchmark_repair_pairs_fc128best.summary.json": "data/processed/benchmark_repair_pairs_fc128best.summary.json",
        "ai4fm_public_seed_file_manifest_v1.summary.json": "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json",
        "ai4fm_public_seed_license_surface.json": "outputs/manifests/ai4fm_public_seed_license_surface.json",
        "ai4fm_public_seed_tla_modules_v1.summary.json": "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json",
        "ai4fm_public_seed_prover_candidates_v1.summary.json": "data/processed/ai4fm_public_seed_prover_candidates_v1.summary.json",
        "ai4fm_public_seed_prover_shape_ready_v1.summary.json": (
            "data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json"
        ),
        "ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json": (
            "data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json"
        ),
        "ai4fm_public_tlaprove_corpora.json": "outputs/manifests/ai4fm_public_tlaprove_corpora.json",
        "ai4fm_public_tlaprove_import_all_public_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_all_public_v1.summary.json",
        "ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json",
        "chattla_tla_prover_sft_public_all_v1.summary.json": "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json",
        "ai4fm_public_tlaprove_import_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_v1.summary.json",
        "ai4fm_public_tlaprove_import_raw_v1.summary.json": "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json",
        "chattla_tla_prover_sft_public_expanded_v1.summary.json": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json",
        "chattla_tla_prover_sft_v1.summary.json": "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        "formalllm_eval_v1.summary.json": "data/processed/formalllm_eval_v1.summary.json",
        "hf_publish_readiness.chattla_20b_fc128best.json": (
            "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json"
        ),
        "hf_publish_readiness.json": "outputs/manifests/hf_publish_readiness.json",
        "prover_eval.summary.json": "data/processed/prover_eval.summary.json",
        "sany_tlc_pass_corpus_diagnostic.json": "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json",
        "sany_tlc_pass_eval_v1.summary.json": "data/processed/sany_tlc_pass_eval_v1.summary.json",
        "sany_tlc_pass_sft_v1.summary.json": "data/processed/sany_tlc_pass_sft_v1.summary.json",
        "tla_prover_artifacts_v1.json": "outputs/manifests/tla_prover_artifacts_v1.json",
        "tla_prover_corpus_preflight.json": "outputs/manifests/tla_prover_corpus_preflight.json",
        "tla_prover_corpus_experiment_matrix.json": (
            "outputs/manifests/tla_prover_corpus_experiment_matrix.json"
        ),
        "tla_prover_full_dataset_failure_analysis.json": (
            "outputs/manifests/tla_prover_full_dataset_failure_analysis.json"
        ),
        "tlaps_verified_autoprover_traces_v1.summary.json": "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json",
    }


def _find_public_dataset_layer_count_mismatch(readme_text: str) -> tuple[int, int] | None:
    match = re.search(
        r"ChatTLA currently tracks\s+([A-Za-z0-9]+)\s+public AI4FM-aligned data/artifact layers",
        readme_text,
    )
    if not match:
        return None
    declared_raw = match.group(1).lower()
    declared = int(declared_raw) if declared_raw.isdigit() else COUNT_WORDS.get(declared_raw)
    if declared is None:
        return None
    start = readme_text.find("## Public Datasets")
    if start == -1:
        section = readme_text
    else:
        end_marker = "Rebuild the public AI4FM artifacts with:"
        end = readme_text.find(end_marker, start)
        section = readme_text[start:end] if end != -1 else readme_text[start:]
    table_rows = sum(1 for line in section.splitlines() if line.startswith("| `"))
    if declared != table_rows:
        return declared, table_rows
    return None


def _expected_snippets(repo: Path) -> dict[str, list[str]]:
    formalllm = _read_json(repo / "data/processed/formalllm_eval_v1.summary.json")
    tlaprove = _read_json(repo / "outputs/manifests/ai4fm_public_tlaprove_corpora.json")
    tlaprove_import_all_public = _read_json(
        repo / "data/processed/ai4fm_public_tlaprove_import_all_public_v1.summary.json"
    )
    tlaprove_import_all_public_raw = _read_json(
        repo / "data/processed/ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json"
    )
    tlaprove_import = _read_json(repo / "data/processed/ai4fm_public_tlaprove_import_v1.summary.json")
    tlaprove_import_raw = _read_json(repo / "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json")
    seed_files = _read_json(repo / "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json")
    seed_modules = _read_json(repo / "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json")
    seed_candidates = _read_json(repo / "data/processed/ai4fm_public_seed_prover_candidates_v1.summary.json")
    mixed_sft = _read_json(repo / "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json")
    expanded_sft = _read_json(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json"
    )
    full_public_expanded_sft = _read_json(
        repo / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json"
    )
    org_surface = _read_json(repo / "outputs/manifests/ai4fm_org_surface.json")
    seed_license_surface = _read_json(repo / "outputs/manifests/ai4fm_public_seed_license_surface.json")
    dataset_surface = _read_json(repo / "outputs/manifests/ai4fm_public_dataset_surface.json")
    corpus_preflight = _read_json(repo / "outputs/manifests/tla_prover_corpus_preflight.json")
    readiness = _read_json(repo / "outputs/manifests/hf_publish_readiness.json")
    readiness_fc128best = _read_json(repo / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json")
    repair_pairs_summary = _read_json(repo / "data/processed/benchmark_repair_pairs_fc128best.summary.json")

    formalllm_rows = int(formalllm["rows"])
    formalllm_families = int(formalllm["families_seen"])
    raw_rows = int(tlaprove["aggregate"]["total_public_jsonl_rows"])
    largest = tlaprove["aggregate"]["largest_public_jsonl"]
    largest_name = Path(str(largest["path"])).name
    largest_rows = int(largest["rows"])
    normalized_rows = int(tlaprove_import["kept_rows"])
    raw_import_rows = int(tlaprove_import_raw["kept_rows"])
    all_public_normalized_rows = int(tlaprove_import_all_public["kept_rows"])
    all_public_raw_rows = int(tlaprove_import_all_public_raw["kept_rows"])
    all_public_rows = int(tlaprove["aggregate"].get("all_public_jsonl_rows", raw_rows))
    all_public_files = int(tlaprove["aggregate"].get("all_public_jsonl_files", 0))
    tracked_public_files = int(tlaprove["aggregate"].get("tracked_public_jsonl_files", 0))
    org_public_repo_count = int(org_surface["public_repo_count"])
    org_corpus_relevant_repo_count = int(org_surface["summary"]["corpus_relevant_repo_count"])
    seed_repo_inputs = int(seed_files["seed_repo_inputs"])
    seed_totals = seed_files.get("totals", {})
    tracked_seed_files = int(seed_totals.get("all", seed_files.get("kept_rows", 0)))
    raw_tla_files = int(seed_totals["tla"])
    usable_module_rows = int(seed_modules.get("rows", seed_modules["kept_rows"]))
    candidate_rows = int(seed_candidates["kept_rows"])
    mixed_sft_rows = int(mixed_sft["total_rows"])
    expanded_sft_rows = int(expanded_sft["total_rows"])
    expanded_public_import_rows = int(expanded_sft["public_import_rows"])
    expanded_seed_candidate_rows = int(expanded_sft["public_seed_candidates_rows"])
    full_public_expanded_sft_rows = int(full_public_expanded_sft["total_rows"])
    full_public_expanded_public_import_rows = int(full_public_expanded_sft["public_import_rows"])
    license_repo_counts = seed_license_surface["license_summary"]["repo_counts"]
    permissive_repo_count = int(seed_license_surface["license_summary"]["clearly_permissive_repo_count"])
    caution_repo_count = int(seed_license_surface["license_summary"]["caution_repo_count"])
    apache_repos = int(license_repo_counts.get("Apache-2.0", 0))
    mit_repos = int(license_repo_counts.get("MIT", 0))
    noassertion_repos = int(license_repo_counts.get("NOASSERTION", 0))
    unknown_repos = int(license_repo_counts.get("UNKNOWN", 0))
    pull_files = int(dataset_surface["pipeline"]["pull"]["nfiles"])
    parsed_artifacts = int(dataset_surface["pipeline"]["parse_output"]["nfiles"])
    formalllm_coverage = corpus_preflight["formalllm_coverage"]
    coverage_rows = int(formalllm_coverage["formalllm_rows"])
    coverage_corpora = {Path(corpus["path"]).name: corpus for corpus in formalllm_coverage["corpora"]}
    default_coverage_rows = int(coverage_corpora["chattla_tla_prover_sft_v1.jsonl"]["rows"])
    expanded_coverage_rows = int(coverage_corpora["chattla_tla_prover_sft_public_expanded_v1.jsonl"]["rows"])
    full_public_coverage_rows = int(coverage_corpora["chattla_tla_prover_sft_public_all_v1.jsonl"]["rows"])
    canonical_blockers = readiness.get("blockers", [])
    canonical_no_core_rows = int(readiness["failure_surface"]["aggregate"]["rows_with_no_core_components"])
    fc128best_blockers = readiness_fc128best.get("blockers", [])
    fc128best_no_core_rows = int(readiness_fc128best["failure_surface"]["aggregate"]["rows_with_no_core_components"])
    fc128best_placeholder_rows = int(
        readiness_fc128best["failure_surface"]["red_flags"]["obvious_placeholder_rows"]
    )
    repair_pair_rows = int(repair_pairs_summary["rows"])
    repair_failed_rows_seen = int(repair_pairs_summary["failed_rows_seen"])
    repair_gold_coverage = int(repair_pairs_summary["gold_coverage"]["covered_failed_rows"])
    repair_missing_gold = len(repair_pairs_summary["gold_coverage"]["missing_gold_benchmark_ids"])

    return {
        "README.md": [
            (
                "ChatTLA currently tracks eight public AI4FM-aligned data/artifact layers spanning "
                f"the {formalllm_rows}-example `FormaLLM` benchmark, a {_comma(raw_rows)}-row tracked `TLA-Prove` training/eval slice within a "
                f"{_comma(all_public_rows)}-row committed public JSONL surface, and a {_comma(raw_tla_files)}-file / "
                f"{_comma(usable_module_rows)}-module public seed-repo surface:"
            ),
            f"| `FormaLLM` | {formalllm_rows} canonical prompt/spec entries across {formalllm_families} families |",
            (
                "| `TLA-Prove public corpora` | "
                f"{_comma(raw_rows)} JSONL rows across the tracked public training/eval corpora; "
                f"the full committed public JSONL surface currently spans {_comma(all_public_rows)} rows across {all_public_files} files |"
            ),
            (
                "| `TLA-Prove normalized import` | "
                f"{_comma(normalized_rows)} deduplicated ChatTLA-format rows built from the committed public corpora |"
            ),
            (
                "| `TLA-Prove raw import` | "
                f"{_comma(raw_import_rows)} undeduped ChatTLA-format rows spanning the full tracked public corpora slice |"
            ),
            (
                "| `tla-dataset-pipeline seed repo files` | "
                f"{_comma(tracked_seed_files)} tracked `.tla` / `.cfg` / `.tlaps` files across the {seed_repo_inputs} committed public seed repos, "
                f"including {_comma(raw_tla_files)} `.tla` files |"
            ),
            (
                "| `tla-dataset-pipeline seed prover candidates` | "
                f"{_comma(candidate_rows)} SANY-clean prover-candidate rows from {_comma(usable_module_rows)} usable public seed-module rows |"
            ),
            (
                "| `tla-dataset-pipeline` | "
                f"{_comma(pull_files)} extracted raw files and {_comma(parsed_artifacts)} parsed artifacts in the public DVC surface |"
            ),
            (
                "The older `1800+` FormaLLM wording comes from a stale architecture-doc note, not the current committed public metadata; "
                f"ChatTLA treats the live `{formalllm_rows}`-entry `all_models.json` and `Input/{{train,val,test}}.json` split files as the canonical public FormaLLM surface."
            ),
            (
                "The verifier-backed preflight manifest at "
                "`outputs/manifests/tla_prover_corpus_preflight.json` now proves exact `205/205` `FormaLLM` row coverage across the default, expanded, and full-public prover train corpora rather than relying on summary counts alone."
            ),
            (
                "The current fresh-benchmark repair curriculum for that blocked `fc128best` lane is summarized in "
                f"`data/processed/benchmark_repair_pairs_fc128best.summary.json`: `{repair_pair_rows}` repair pairs cover "
                f"`{repair_gold_coverage}/{repair_failed_rows_seen}` failed benchmark rows, leaving only "
                f"`{repair_pairs_summary['gold_coverage']['missing_gold_benchmark_ids'][0]}` without a public gold target today."
            ),
            (
                "If someone cites a public AI4FM GitHub surface of `1,800+`, the reproducible interpretation today is the broader expansion lanes above: "
                f"`{_comma(all_public_rows)}` committed `TLA-Prove` JSONL rows, `{_comma(raw_tla_files)}` public seed `.tla` files, "
                f"and `{_comma(usable_module_rows)}` usable seed modules."
            ),
            (
                f"Repo-level license provenance across the `{seed_repo_inputs}` committed public seed repos is mixed: "
                f"`{apache_repos}` Apache-2.0, `{mit_repos}` MIT, `{noassertion_repos}` NOASSERTION, and `{unknown_repos}` unknown."
            ),
            (
                f"Only the `{formalllm_rows}`-row `FormaLLM` layer currently feeds `chattla_tla_prover_sft_v1`;"
                " the `TLA-Prove` and seed-repo lanes above are audited public expansion artifacts, not yet mixed into that prover corpus."
            ),
            (
                "There is now an explicit non-default expansion build path as well: "
                "`data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl` carries the current "
                f"`{mixed_sft_rows}`-row prover SFT stack plus the `{expanded_public_import_rows}`-row normalized public "
                f"`TLA-Prove` import and `{expanded_seed_candidate_rows}` public seed prover-candidate replays for "
                f"`{expanded_sft_rows}` total rows."
            ),
            (
                "The broader committed-public variant is now materialized too: "
                "`data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl` carries the same prover "
                f"stack plus the `{full_public_expanded_public_import_rows}`-row full-public normalized import for "
                f"`{full_public_expanded_sft_rows}` total rows."
            ),
            (
                f"The full tracked-corpora public row lane is also materialized at "
                f"`data/processed/ai4fm_public_tlaprove_import_raw_v1.jsonl` with `{raw_import_rows}` rows "
                "when we need the undeduped AI4FM public import surface."
            ),
        ],
        "docs/AI4FM_PUBLIC_DATASET_SURFACE.md": [
            f"- `{formalllm_rows}` canonical metadata entries",
            f"- public JSONL rows across the tracked training/eval corpora: `{raw_rows}`",
            f"- `{raw_import_rows}` kept rows in `ai4fm_public_tlaprove_import_raw_v1` when exact-final-spec dedupe is disabled",
            f"- full committed public JSONL surface: `{all_public_rows}` rows across `{all_public_files}` files",
            f"- `ai4fm_public_seed_file_manifest_v1.summary.json` reports `{raw_tla_files}` public",
            f"- `ai4fm_public_seed_tla_modules_v1.summary.json` reports `{usable_module_rows}` usable",
            f"- `{permissive_repo_count}` repos with clearly permissive SPDX labels at the repo level, versus `{caution_repo_count}` redistribution-caution repos",
            f"- `{raw_rows}` raw public rows across the tracked corpora",
            f"- `{normalized_rows}` kept ChatTLA-format rows after normalization and exact final-spec dedupe",
            (
                f"- if someone cites `1800+` for the current public AI4FM GitHub surface, the closest reproducible interpretations today are the broader expansion lanes: "
                f"`{all_public_rows}` committed `TLA-Prove` JSONL rows, `{raw_tla_files}` public seed `.tla` files, or `{usable_module_rows}` usable seed modules"
            ),
        ],
        "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md": [
            "This bundle ships prover corpora plus metadata summaries for the broader public AI4FM expansion lanes.",
            f"- `metadata/formalllm_eval_v1.summary.json`: full `FormaLLM` canonical prompt/spec",
            f"  layer (`{formalllm_rows}` rows).",
            (
                f"- `metadata/tla_prover_corpus_preflight.json`: schema preflight plus exact `{coverage_rows}/{coverage_rows}` `FormaLLM` row\n"
                f"  coverage verification across the `{default_coverage_rows}`-row default, `{expanded_coverage_rows}`-row expanded, and\n"
                f"  `{full_public_coverage_rows}`-row full-public prover train corpora."
            ),
            (
                f"- `metadata/ai4fm_org_surface.json`: live public GitHub org snapshot "
                f"(`{org_public_repo_count}` repos,\n"
                f"  `{org_corpus_relevant_repo_count}` corpus-relevant)."
            ),
            (
                f"- `metadata/ai4fm_public_tlaprove_corpora.json`: public AI4FM TLA-Prove corpus\n"
                f"  report (`{raw_rows}` tracked training/eval rows within a `{all_public_rows}`-row committed public\n"
                "  JSONL surface)."
            ),
            (
                f"- `metadata/ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json`: raw\n"
                f"  full-public import summary (`{all_public_raw_rows}` undeduped rows)."
            ),
            (
                f"- `metadata/ai4fm_public_tlaprove_import_all_public_v1.summary.json`: normalized\n"
                f"  full-public import layer (`{all_public_normalized_rows}` rows)."
            ),
            (
                f"- `metadata/ai4fm_public_tlaprove_import_raw_v1.summary.json`: raw tracked-corpora\n"
                f"  import summary (`{raw_import_rows}` undeduped rows)."
            ),
            (
                "- `metadata/ai4fm_public_seed_file_manifest_v1.summary.json`: public GitHub seed\n"
                f"  file manifest (`{tracked_seed_files}` tracked files, `{raw_tla_files}` `.tla` files, `{usable_module_rows}` usable module rows)."
            ),
            (
                f"- `metadata/ai4fm_public_seed_tla_modules_v1.summary.json`: usable public `.tla`\n"
                f"  module corpus (`{usable_module_rows}` rows)."
            ),
            (
                f"- `metadata/ai4fm_public_seed_license_surface.json`: repo-level SPDX/provenance\n"
                f"  rollup for the `{seed_repo_inputs}` committed public seed repos."
            ),
            (
                f"- `metadata/hf_publish_readiness.json`: canonical publish-readiness gate (`{len(canonical_blockers)}`\n"
                f"  blockers; `{canonical_no_core_rows}` latest benchmark rows still missing every core TLA component)."
            ),
            (
                "- `metadata/hf_publish_readiness.chattla_20b_fc128best.json`: fresh `fc128best`\n"
                f"  publish-readiness gate (`{len(fc128best_blockers)}` blocker; `{fc128best_no_core_rows}` rows still missing every core component,\n"
                f"  `{fc128best_placeholder_rows}` with obvious placeholder text)."
            ),
            (
                "- `metadata/benchmark_repair_pairs_fc128best.summary.json`: benchmark-derived\n"
                f"  repair curriculum summary (`{repair_pair_rows}` rows covering `{repair_gold_coverage}` of `{repair_failed_rows_seen}` failed fresh-benchmark\n"
                f"  cases; `{repair_missing_gold}` missing gold target)."
            ),
            f"- Mixed prover SFT corpus: `{mixed_sft_rows}` rows",
            (
                f"- `metadata/chattla_tla_prover_sft_public_expanded_v1.summary.json`: non-default\n"
                f"  public-AI4FM expanded prover SFT summary (`{expanded_sft_rows}` rows total; "
                f"`{expanded_public_import_rows}` normalized import rows + `{expanded_seed_candidate_rows}` seed prover-candidate replays on top of the baseline prover stack)."
            ),
            (
                f"- `metadata/chattla_tla_prover_sft_public_all_v1.summary.json`: full-public\n"
                f"  expanded prover SFT summary (`{full_public_expanded_sft_rows}` rows total; "
                f"`{full_public_expanded_public_import_rows}` normalized full-public import rows on top of the baseline prover stack)."
            ),
            (
                f"- `metadata/tla_prover_corpus_experiment_matrix.json`: bounded corpus-lane\n"
                f"  comparison matrix covering the `{mixed_sft_rows}`-row baseline, `{expanded_sft_rows}`-row expanded lane,\n"
                f"  `{full_public_expanded_sft_rows}`-row full-public lane, and the `{candidate_rows}`/`{usable_module_rows}` public seed funnel."
            ),
            f"- Public AI4FM normalized import: `{normalized_rows}` rows from the tracked `{raw_rows}`-row",
            "  public corpora slice.",
            (
                f"- Public seed repo license surface: `{apache_repos}` Apache-2.0 repos, `{mit_repos}` MIT repos, `{noassertion_repos}`\n"
                f"  NOASSERTION repos, and `{unknown_repos}` unknown-license repos."
            ),
            (
                f"- Public AI4FM seed-module prover candidates: `{candidate_rows}` rows out of `{usable_module_rows}` usable\n"
                "  public seed-module rows."
            ),
            (
                f"- Canonical publish readiness gate: blocked, with `{canonical_no_core_rows}` of `{canonical_no_core_rows}` latest benchmark rows\n"
                "  missing every core TLA component."
            ),
            (
                f"- `fc128best` publish readiness gate: blocked, with `{fc128best_no_core_rows}` of `{fc128best_no_core_rows}` rows missing every core component\n"
                f"  and `{fc128best_placeholder_rows}` obvious-placeholder failures."
            ),
            (
                f"- Benchmark-derived repair curriculum: `{repair_pair_rows}` rows covering `{repair_gold_coverage}` of `{repair_failed_rows_seen}`\n"
                f"  failed fresh-benchmark cases, with `{repair_missing_gold}` missing gold target."
            ),
            (
                "The AI4FM import and seed-repo lanes are metadata-only audit surfaces in this bundle; "
                "they are not yet mixed into `data/train/chattla_tla_prover_sft_v1.jsonl`."
            ),
        ],
    }


def build_report(*, repo: Path = REPO) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for rel_path, snippets in _expected_snippets(repo).items():
        path = repo / rel_path
        if not path.exists():
            findings.append({"path": rel_path, "expected": "file to exist"})
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                findings.append({"path": rel_path, "expected": snippet})
        if rel_path == "README.md":
            mismatch = _find_public_dataset_layer_count_mismatch(text)
            if mismatch is not None:
                declared, actual = mismatch
                findings.append(
                    {
                        "path": rel_path,
                        "expected": (
                            "public AI4FM dataset intro count to match the number of dataset table rows "
                            f"(declared {declared}, found {actual})"
                        ),
                    }
                )
    for bundle_name, source_rel in _bundled_metadata_sources(repo).items():
        source_path = repo / source_rel
        bundle_path = repo / BUNDLE_ROOT.relative_to(REPO) / "metadata" / bundle_name
        if not source_path.exists():
            findings.append({"path": source_rel, "expected": "source artifact to exist"})
            continue
        if not bundle_path.exists():
            findings.append(
                {
                    "path": str(bundle_path.relative_to(repo)),
                    "expected": f"bundled copy of {source_rel}",
                }
            )
            continue
        if bundle_path.read_text(encoding="utf-8") != source_path.read_text(encoding="utf-8"):
            findings.append(
                {
                    "path": str(bundle_path.relative_to(repo)),
                    "expected": f"exact content match for {source_rel}",
                }
            )
    return {
        "ok": not findings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
        "repo": str(repo),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    args = parser.parse_args()

    report = build_report(repo=args.repo)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
