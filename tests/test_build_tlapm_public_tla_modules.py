import json
from pathlib import Path

from scripts.build_tlapm_public_tla_modules import build_tlapm_tla_modules, write_outputs


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_tlapm_tla_modules_extracts_library_rows(tmp_path: Path) -> None:
    tlapm_root = tmp_path / "tlapm"
    library = tlapm_root / "library"
    _write(library / "FiniteSetTheorems.tla", "---- MODULE FiniteSetTheorems ----\nEXTENDS Functions\n====\n")
    _write(library / "FiniteSetTheorems_proofs.tla", "---- MODULE FiniteSetTheorems_proofs ----\n====\n")
    _write(library / "README.tla", "\\* helper text without module header\n")

    rows, summary = build_tlapm_tla_modules(
        tlapm_root=tlapm_root,
        generated_at="2026-06-29T00:00:00+00:00",
    )

    assert [row["module"] for row in rows] == ["FiniteSetTheorems", "FiniteSetTheorems_proofs"]
    assert rows[0]["repo"] == "tlaplus/tlapm"
    assert rows[0]["source_path"].endswith("library/FiniteSetTheorems.tla")
    assert rows[0]["content_sha256"]
    assert rows[0]["repo_head_sha"] is None
    assert summary["kept_rows"] == 2
    assert summary["tla_candidates"] == 3
    assert summary["skipped_missing_module_header"] == 1


def test_write_outputs_handles_out_of_repo_target(tmp_path: Path) -> None:
    rows = [
        {
            "repo": "tlaplus/tlapm",
            "module": "FiniteSetTheorems",
            "source_path": "data/external/tlapm/library/FiniteSetTheorems.tla",
            "content": "---- MODULE FiniteSetTheorems ----\n====\n",
        }
    ]
    summary = {"kept_rows": 1}
    out = tmp_path / "tlapm_public_tla_modules_v1.jsonl"

    final_summary = write_outputs(rows, summary, out)

    assert final_summary["out"] == str(out)
    assert final_summary["summary"] == str(out.with_suffix(".summary.json"))
