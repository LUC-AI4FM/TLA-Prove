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
    dataset_surface = _read_json(repo / "outputs/manifests/ai4fm_public_dataset_surface.json")

    formalllm_rows = int(formalllm["rows"])
    formalllm_families = int(formalllm["families_seen"])
    raw_rows = int(tlaprove["aggregate"]["total_public_jsonl_rows"])
    largest = tlaprove["aggregate"]["largest_public_jsonl"]
    largest_name = Path(str(largest["path"])).name
    largest_rows = int(largest["rows"])
    normalized_rows = int(tlaprove_import["kept_rows"])
    seed_repo_inputs = int(seed_files["seed_repo_inputs"])
    raw_tla_files = int(seed_files["totals"]["tla"])
    usable_module_rows = int(seed_modules.get("rows", seed_modules["kept_rows"]))
    pull_files = int(dataset_surface["pipeline"]["pull"]["nfiles"])
    parsed_artifacts = int(dataset_surface["pipeline"]["parse_output"]["nfiles"])

    return {
        "README.md": [
            (
                "ChatTLA currently uses seven public AI4FM-aligned corpus layers spanning "
                f"the {formalllm_rows}-example `FormaLLM` benchmark, {_comma(raw_rows)} raw public "
                f"`TLA-Prove` JSONL rows, and a {_comma(raw_tla_files)}-file / "
                f"{_comma(usable_module_rows)}-module public seed-repo surface:"
            ),
            f"| `FormaLLM` | {formalllm_rows} canonical prompt/spec entries across {formalllm_families} families |",
            (
                "| `TLA-Prove public corpora` | "
                f"{_comma(raw_rows)} JSONL rows across committed public corpora; "
                f"largest single corpus is `{largest_name}` with {_comma(largest_rows)} rows |"
            ),
            (
                "| `TLA-Prove normalized import` | "
                f"{_comma(normalized_rows)} deduplicated ChatTLA-format rows built from the committed public corpora |"
            ),
            (
                "| `tla-dataset-pipeline seed repo files` | "
                f"3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the {seed_repo_inputs} committed public seed repos, "
                f"including {_comma(raw_tla_files)} `.tla` files |"
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
                "The seed prover-candidate corpus is the first stricter bridge from the "
                f"{_comma(raw_tla_files)} public `.tla` files / {_comma(usable_module_rows)} usable module rows into the current prover lane"
            ),
        ],
        "docs/AI4FM_PUBLIC_DATASET_SURFACE.md": [
            f"- `{formalllm_rows}` canonical metadata entries",
            f"- public JSONL rows across the tracked corpora: `{raw_rows}`",
            f"- `ai4fm_public_seed_file_manifest_v1.summary.json` reports `{raw_tla_files}` public",
            f"- `ai4fm_public_seed_tla_modules_v1.summary.json` reports `{usable_module_rows}` usable",
            f"- `{raw_rows}` raw public rows across the committed corpora",
            f"- `{normalized_rows}` kept ChatTLA-format rows after normalization and exact final-spec dedupe",
        ],
    }


def build_report(*, repo: Path = REPO) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for rel_path, snippets in _expected_snippets(repo).items():
        text = (repo / rel_path).read_text(encoding="utf-8")
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
