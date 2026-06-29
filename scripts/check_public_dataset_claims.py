#!/usr/bin/env python3
"""Validate that public dataset claims in README/docs match tracked manifests."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _comma(value: int) -> str:
    return f"{value:,}"


def _expected_snippets(repo: Path) -> dict[str, list[str]]:
    formalllm = _read_json(repo / "data/processed/formalllm_eval_v1.summary.json")
    tlaprove = _read_json(repo / "outputs/manifests/ai4fm_public_tlaprove_corpora.json")
    tlaprove_import = _read_json(repo / "data/processed/ai4fm_public_tlaprove_import_v1.summary.json")
    seed_files = _read_json(repo / "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json")
    seed_modules = _read_json(repo / "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json")
    seed_candidates = _read_json(repo / "data/processed/ai4fm_public_seed_prover_candidates_v1.summary.json")
    mixed_sft = _read_json(repo / "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json")
    dataset_surface = _read_json(repo / "outputs/manifests/ai4fm_public_dataset_surface.json")

    formalllm_rows = int(formalllm["rows"])
    formalllm_families = int(formalllm["families_seen"])
    raw_rows = int(tlaprove["aggregate"]["total_public_jsonl_rows"])
    largest = tlaprove["aggregate"]["largest_public_jsonl"]
    largest_name = Path(str(largest["path"])).name
    largest_rows = int(largest["rows"])
    normalized_rows = int(tlaprove_import["kept_rows"])
    all_public_rows = int(tlaprove["aggregate"].get("all_public_jsonl_rows", raw_rows))
    all_public_files = int(tlaprove["aggregate"].get("all_public_jsonl_files", 0))
    tracked_public_files = int(tlaprove["aggregate"].get("tracked_public_jsonl_files", 0))
    seed_repo_inputs = int(seed_files["seed_repo_inputs"])
    seed_totals = seed_files.get("totals", {})
    tracked_seed_files = int(seed_totals.get("all", seed_files.get("kept_rows", 0)))
    raw_tla_files = int(seed_totals["tla"])
    usable_module_rows = int(seed_modules.get("rows", seed_modules["kept_rows"]))
    candidate_rows = int(seed_candidates["kept_rows"])
    mixed_sft_rows = int(mixed_sft["total_rows"])
    pull_files = int(dataset_surface["pipeline"]["pull"]["nfiles"])
    parsed_artifacts = int(dataset_surface["pipeline"]["parse_output"]["nfiles"])

    return {
        "README.md": [
            (
                "ChatTLA currently uses seven public AI4FM-aligned data/artifact layers spanning "
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
                "If someone cites a public AI4FM GitHub surface of `1,800+`, the reproducible interpretation today is the broader expansion lanes above: "
                f"`{_comma(all_public_rows)}` committed `TLA-Prove` JSONL rows, `{_comma(raw_tla_files)}` public seed `.tla` files, "
                f"and `{_comma(usable_module_rows)}` usable seed modules."
            ),
            (
                "The seed prover-candidate corpus is the first stricter bridge from the "
                f"{_comma(raw_tla_files)} public `.tla` files / {_comma(usable_module_rows)} usable module rows into the current prover lane"
            ),
        ],
        "docs/AI4FM_PUBLIC_DATASET_SURFACE.md": [
            f"- `{formalllm_rows}` canonical metadata entries",
            f"- public JSONL rows across the tracked training/eval corpora: `{raw_rows}`",
            f"- full committed public JSONL surface: `{all_public_rows}` rows across `{all_public_files}` files",
            f"- `ai4fm_public_seed_file_manifest_v1.summary.json` reports `{raw_tla_files}` public",
            f"- `ai4fm_public_seed_tla_modules_v1.summary.json` reports `{usable_module_rows}` usable",
            f"- `{raw_rows}` raw public rows across the tracked corpora",
            f"- `{normalized_rows}` kept ChatTLA-format rows after normalization and exact final-spec dedupe",
            (
                f"- if someone cites `1800+` for the current public AI4FM GitHub surface, the closest reproducible interpretations today are the broader expansion lanes: "
                f"`{all_public_rows}` committed `TLA-Prove` JSONL rows, `{raw_tla_files}` public seed `.tla` files, or `{usable_module_rows}` usable seed modules"
            ),
        ],
        "outputs/hf_publish/chattla-tla-prover-corpora-v1/README.md": [
            f"- `metadata/formalllm_eval_v1.summary.json`: full `FormaLLM` canonical prompt/spec",
            f"  layer (`{formalllm_rows}` rows).",
            (
                f"- `metadata/ai4fm_public_tlaprove_corpora.json`: public AI4FM TLA-Prove corpus\n"
                f"  report (`{raw_rows}` tracked training/eval rows within a `{all_public_rows}`-row committed public\n"
                "  JSONL surface)."
            ),
            (
                "- `metadata/ai4fm_public_seed_file_manifest_v1.summary.json`: public GitHub seed\n"
                f"  file manifest (`{tracked_seed_files}` tracked files, `{raw_tla_files}` `.tla` files, `{usable_module_rows}` usable module rows)."
            ),
            f"- Mixed prover SFT corpus: `{mixed_sft_rows}` rows",
            f"- Public AI4FM normalized import: `{normalized_rows}` rows from the tracked `{raw_rows}`-row",
            "  public corpora slice.",
            (
                f"- Public AI4FM seed-module prover candidates: `{candidate_rows}` rows out of `{usable_module_rows}` usable\n"
                "  public seed-module rows."
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
