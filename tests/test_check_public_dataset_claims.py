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
        json.dumps({"seed_repo_inputs": 11, "totals": {"tla": 2110}}),
    )
    _write(
        repo / "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json",
        json.dumps({"kept_rows": 2108}),
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
                "ChatTLA currently uses seven public AI4FM-aligned corpus layers spanning the 205-example `FormaLLM` benchmark, 2,350 raw public `TLA-Prove` JSONL rows, and a 2,110-file / 2,108-module public seed-repo surface:",
                "| `FormaLLM` | 205 canonical prompt/spec entries across 71 families |",
                "| `TLA-Prove public corpora` | 2,350 JSONL rows across committed public corpora; largest single corpus is `diamond_sft_v3.jsonl` with 1,053 rows |",
                "| `TLA-Prove normalized import` | 1,005 deduplicated ChatTLA-format rows built from the committed public corpora |",
                "| `tla-dataset-pipeline seed repo files` | 3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the 11 committed public seed repos, including 2,110 `.tla` files |",
                "| `tla-dataset-pipeline` | 2,628 extracted raw files and 3,979 parsed artifacts in the public DVC surface |",
                "The older `1800+` FormaLLM wording comes from a stale architecture-doc note, not the current committed public metadata; ChatTLA treats the live `205`-entry `all_models.json` and `Input/{train,val,test}.json` split files as the canonical public FormaLLM surface.",
                "The seed prover-candidate corpus is the first stricter bridge from the 2,110 public `.tla` files / 2,108 usable module rows into the current prover lane.",
            ]
        ),
    )
    _write(
        tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md",
        "\n".join(
            [
                "- `205` canonical metadata entries",
                "- public JSONL rows across the tracked corpora: `2350`",
                "- `ai4fm_public_seed_file_manifest_v1.summary.json` reports `2110` public",
                "- `ai4fm_public_seed_tla_modules_v1.summary.json` reports `2108` usable",
                "- `2350` raw public rows across the committed corpora",
                "- `1005` kept ChatTLA-format rows after normalization and exact final-spec dedupe",
            ]
        ),
    )

    report = build_report(repo=tmp_path)

    assert report["ok"] is True
    assert report["findings"] == []


def test_build_report_flags_mismatched_public_claims(tmp_path: Path) -> None:
    _write_manifests(tmp_path)
    _write(tmp_path / "README.md", "FormaLLM benchmark has 204 rows.\n")
    _write(tmp_path / "docs/AI4FM_PUBLIC_DATASET_SURFACE.md", "public JSONL rows across the tracked corpora: `9999`\n")

    report = build_report(repo=tmp_path)

    assert report["ok"] is False
    assert any("205 canonical prompt/spec entries across 71 families" in finding["expected"] for finding in report["findings"])
    assert any("public JSONL rows across the tracked corpora: `2350`" in finding["expected"] for finding in report["findings"])
