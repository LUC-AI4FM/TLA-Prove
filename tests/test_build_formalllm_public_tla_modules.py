import json
from pathlib import Path

from scripts.build_formalllm_public_tla_modules import build_formalllm_tla_modules, write_outputs


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_formalllm_tla_modules_extracts_module_rows(tmp_path: Path) -> None:
    formalllm_root = tmp_path / "FormaLLM" / "data"
    family = formalllm_root / "FamilyOne" / "tla"
    _write(family / "Alpha.tla", "---- MODULE Alpha ----\nEXTENDS Naturals\n====\n")
    _write(family / "Alpha_clean.tla", "---- MODULE Alpha ----\nEXTENDS Naturals\n====\n")
    _write(family / "HelperOnly.tla", "\\* helper text without module header\n")

    rows, summary = build_formalllm_tla_modules(
        formalllm_root=formalllm_root,
        generated_at="2026-06-29T00:00:00+00:00",
    )

    assert [row["module"] for row in rows] == ["Alpha", "Alpha"]
    assert rows[0]["family"] == "FamilyOne"
    assert rows[0]["repo"] == "formalllm/public"
    assert rows[0]["source_path"].endswith("Alpha.tla")
    assert rows[0]["content_sha256"]
    assert summary["kept_rows"] == 2
    assert summary["tla_candidates"] == 3
    assert summary["skipped_missing_module_header"] == 1
    assert summary["duplicate_modules"] == {"Alpha": 2}


def test_write_outputs_handles_out_of_repo_target(tmp_path: Path) -> None:
    rows = [
        {
            "module": "Alpha",
            "family": "FamilyOne",
            "source_path": "data/FormaLLM/data/FamilyOne/tla/Alpha.tla",
            "content": "---- MODULE Alpha ----\n====\n",
        }
    ]
    summary = {"kept_rows": 1}
    out = tmp_path / "formalllm_public_tla_modules_v1.jsonl"

    final_summary = write_outputs(rows, summary, out)

    assert final_summary["out"] == str(out)
    assert final_summary["summary"] == str(out.with_suffix(".summary.json"))
