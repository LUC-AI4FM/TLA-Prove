import json
from pathlib import Path

from scripts.check_public_dataset_claims import build_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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


def test_build_report_accepts_matching_readme_and_doc_claims(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "ChatTLA currently uses seven public AI4FM-aligned data/artifact layers spanning the 205-example `FormaLLM` benchmark, a 2,350-row tracked `TLA-Prove` training/eval slice within a 2,757-row committed public JSONL surface, and a 2,110-file / 2,108-module public seed-repo surface:",
                "| `FormaLLM` | 205 canonical prompt/spec entries across 71 families |",
                "| `TLA-Prove public corpora` | 2,350 JSONL rows across the tracked public training/eval corpora; the full committed public JSONL surface currently spans 2,757 rows across 19 files |",
                "| `TLA-Prove normalized import` | 1,005 deduplicated ChatTLA-format rows built from the committed public corpora |",
                "| `tla-dataset-pipeline seed repo files` | 3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the 11 committed public seed repos, including 2,110 `.tla` files |",
                "| `tla-dataset-pipeline seed prover candidates` | 98 SANY-clean prover-candidate rows from 2,108 usable public seed-module rows |",
                "| `tla-dataset-pipeline` | 2,628 extracted raw files and 3,979 parsed artifacts in the public DVC surface |",
                "The older `1800+` FormaLLM wording comes from a stale architecture-doc note, not the current committed public metadata; ChatTLA treats the live `205`-entry `all_models.json` and `Input/{train,val,test}.json` split files as the canonical public FormaLLM surface.",
                "If someone cites a public AI4FM GitHub surface of `1,800+`, the reproducible interpretation today is the broader expansion lanes above: `2,757` committed `TLA-Prove` JSONL rows, `2,110` public seed `.tla` files, and `2,108` usable seed modules.",
                "The seed prover-candidate corpus is the first stricter bridge from the 2,110 public `.tla` files / 2,108 usable module rows into the current prover lane.",
            ]
        ),
    )
    _write(
        tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md",
        "\n".join(
            [
                "- `205` canonical metadata entries",
                "- public JSONL rows across the tracked training/eval corpora: `2350`",
                "- full committed public JSONL surface: `2757` rows across `19` files",
                "- `ai4fm_public_seed_file_manifest_v1.summary.json` reports `2110` public",
                "- `ai4fm_public_seed_tla_modules_v1.summary.json` reports `2108` usable",
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
                "- `metadata/formalllm_eval_v1.summary.json`: full `FormaLLM` canonical prompt/spec",
                "  layer (`205` rows).",
                "- `metadata/ai4fm_public_tlaprove_corpora.json`: public AI4FM TLA-Prove corpus",
                "  report (`2350` tracked training/eval rows within a `2757`-row committed public",
                "  JSONL surface).",
                "- `metadata/ai4fm_public_seed_file_manifest_v1.summary.json`: public GitHub seed",
                "  file manifest (`3140` tracked files, `2110` `.tla` files, `2108` usable module rows).",
                "- Mixed prover SFT corpus: `1330` rows",
                "- Public AI4FM normalized import: `1005` rows from the tracked `2350`-row",
                "  public corpora slice.",
                "- Public AI4FM seed-module prover candidates: `98` rows out of `2108` usable",
                "  public seed-module rows.",
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
