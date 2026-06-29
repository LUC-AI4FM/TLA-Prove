import json
import subprocess
from pathlib import Path

from scripts.build_formalllm_public_prover_surface import build_surface


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_surface_joins_formalllm_manifest_with_smoke_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "formalllm_public_module_manifest_v1.jsonl"
    smoke = tmp_path / "full_dataset_smoke.jsonl"
    manifest_rows = [
        {"category": "canonical_clean_tla", "path": "data/FormaLLM/data/Fam/tla/Alpha_clean.tla"},
        {"category": "canonical_variant_tla", "path": "data/FormaLLM/data/Fam/tla/Alpha.tla"},
        {"category": "auxiliary_tla", "path": "data/FormaLLM/data/Fam/toolbox/MC.tla"},
        {"category": "canonical_cfg", "path": "data/FormaLLM/data/Fam/cfg/Alpha.cfg"},
    ]
    smoke_rows = [
        {
            "module_path": "data/FormaLLM/data/Fam/tla/Alpha_clean.tla",
            "status": "skipped",
            "reason": "missing Init/Next",
            "runtime_seconds": 0.1,
        },
        {
            "module_path": "data/FormaLLM/data/Fam/tla/Alpha.tla",
            "status": "tlc_error",
            "reason": "tlc_error",
            "tlc_error": "TLC failed here\nmore",
            "runtime_seconds": 0.2,
        },
    ]
    _write(manifest, "\n".join(json.dumps(row) for row in manifest_rows) + "\n")
    _write(smoke, "\n".join(json.dumps(row) for row in smoke_rows) + "\n")

    rows, summary = build_surface(manifest_path=manifest, smoke_path=smoke)

    assert len(rows) == 4
    assert summary["kept_rows"] == 4
    assert summary["scanned_formalllm_rows"] == 2
    assert summary["repair_candidate_rows"] == 1
    assert summary["category_counts"]["canonical_clean_tla"] == 1
    assert summary["scanned_category_counts"] == {
        "canonical_clean_tla": 1,
        "canonical_variant_tla": 1,
    }
    assert summary["unscanned_category_counts"] == {
        "auxiliary_tla": 1,
        "canonical_cfg": 1,
    }
    assert summary["status_counts"] == {
        "skipped": 1,
        "tlc_error": 1,
    }
    assert summary["status_by_category"]["canonical_variant_tla"]["tlc_error"] == 1
    assert summary["top_skip_reasons"][0]["reason"] == "missing Init/Next"
    assert summary["top_tlc_errors"][0]["error"] == "TLC failed here"


def test_cli_writes_formalllm_public_prover_surface(tmp_path: Path) -> None:
    manifest = tmp_path / "formalllm_public_module_manifest_v1.jsonl"
    smoke = tmp_path / "full_dataset_smoke.jsonl"
    _write(
        manifest,
        json.dumps({"category": "canonical_clean_tla", "path": "data/FormaLLM/data/Fam/tla/Alpha_clean.tla"}) + "\n",
    )
    _write(
        smoke,
        json.dumps(
            {
                "module_path": "data/FormaLLM/data/Fam/tla/Alpha_clean.tla",
                "status": "skipped",
                "reason": "missing Init/Next",
            }
        )
        + "\n",
    )
    out = tmp_path / "formalllm_public_prover_surface_v1.jsonl"
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_formalllm_public_prover_surface.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--manifest",
            str(manifest),
            "--smoke",
            str(smoke),
            "--out",
            str(out),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    stdout = json.loads(result.stdout)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["scanned_in_full_dataset_smoke"] is True
    assert stdout["scanned_formalllm_rows"] == 1
    assert out.with_suffix(".summary.json").exists()
