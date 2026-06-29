import json
import subprocess
from pathlib import Path

from scripts.build_ai4fm_public_seed_prover_shape_corpora import build_shape_corpora


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    _write(path, "\n".join(json.dumps(row) for row in rows) + "\n")


def test_build_shape_corpora_splits_shape_ready_and_non_sany_rows(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    good = {
        "repo": "org/repo-a",
        "source_path": "SpecGood.tla",
        "module": "SpecGood",
        "content_sha256": "good",
        "content": "---- MODULE SpecGood ----\nVARIABLES vars\nInit == TRUE\nNext == TRUE\nSpec == Init /\\ [][Next]_vars\nTypeOK == TRUE\n====\n",
    }
    shape_only = {
        "repo": "org/repo-b",
        "source_path": "SpecRepair.tla",
        "module": "SpecRepair",
        "content_sha256": "repair",
        "content": "---- MODULE SpecRepair ----\nVARIABLES vars\nInit == TRUE\nNext == TRUE\nSpec == Init /\\ [][Next]_vars\nTypeOK == TRUE\n====\n",
    }
    not_shape = {
        "repo": "org/repo-c",
        "source_path": "SpecOther.tla",
        "module": "SpecOther",
        "content_sha256": "other",
        "content": "---- MODULE SpecOther ----\nFoo == TRUE\n====\n",
    }
    _write_jsonl(source, [not_shape, shape_only, good])
    _write_jsonl(candidates, [good])

    shape_rows, shape_summary, repair_rows, repair_summary = build_shape_corpora(
        source=source,
        candidate_source=candidates,
    )

    assert [row["module"] for row in shape_rows] == ["SpecGood", "SpecRepair"]
    assert [row["module"] for row in repair_rows] == ["SpecRepair"]
    assert shape_summary["kept_rows"] == 2
    assert shape_summary["unique_modules"] == 2
    assert repair_summary["kept_rows"] == 1
    assert repair_summary["excluded_sany_clean_rows"] == 1


def test_cli_writes_shape_corpora_and_summaries(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    shape_ready_out = tmp_path / "shape_ready.jsonl"
    repair_out = tmp_path / "shape_ready_not_sany.jsonl"
    _write_jsonl(
        source,
        [
            {
                "repo": "org/repo-a",
                "source_path": "SpecRepair.tla",
                "module": "SpecRepair",
                "content_sha256": "repair",
                "content": "---- MODULE SpecRepair ----\nVARIABLES vars\nInit == TRUE\nNext == TRUE\nSpec == Init /\\ [][Next]_vars\nTypeOK == TRUE\n====\n",
            }
        ],
    )
    _write_jsonl(candidates, [])
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_ai4fm_public_seed_prover_shape_corpora.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--source",
            str(source),
            "--candidate-source",
            str(candidates),
            "--shape-ready-out",
            str(shape_ready_out),
            "--shape-ready-not-sany-out",
            str(repair_out),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    stdout = json.loads(result.stdout)
    assert stdout["shape_ready"]["out"] == str(shape_ready_out)
    assert stdout["shape_ready"]["kept_rows"] == 1
    assert stdout["shape_ready_not_sany"]["out"] == str(repair_out)
    assert stdout["shape_ready_not_sany"]["kept_rows"] == 1
    assert shape_ready_out.with_suffix(".summary.json").exists()
    assert repair_out.with_suffix(".summary.json").exists()
