import json
import subprocess
from pathlib import Path

from scripts.inspect_ai4fm_public_seed_prover_funnel import build_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    _write(path, "\n".join(json.dumps(row) for row in rows) + "\n")


def test_build_report_summarizes_seed_module_funnel(tmp_path: Path) -> None:
    source = tmp_path / "ai4fm_public_seed_tla_modules_v1.jsonl"
    source_summary = tmp_path / "ai4fm_public_seed_tla_modules_v1.summary.json"
    candidates = tmp_path / "ai4fm_public_seed_prover_candidates_v1.jsonl"
    candidate_summary = tmp_path / "ai4fm_public_seed_prover_candidates_v1.summary.json"

    _write_jsonl(
        source,
        [
            {
                "module": "SpecGood",
                "repo": "org/repo-a",
                "source_path": "SpecGood.tla",
                "content": "---- MODULE SpecGood ----\nVARIABLES vars\nInit == TRUE\nNext == TRUE\nSpec == Init /\\ [][Next]_vars\nTypeOK == TRUE\n====\n",
            },
            {
                "module": "SpecNeedsTypeOK",
                "repo": "org/repo-a",
                "source_path": "SpecNeedsTypeOK.tla",
                "content": "---- MODULE SpecNeedsTypeOK ----\nVARIABLES vars\nInit == TRUE\nNext == TRUE\nSpec == Init /\\ [][Next]_vars\n====\n",
            },
            {
                "module": "SpecMissingMost",
                "repo": "org/repo-b",
                "source_path": "SpecMissingMost.tla",
                "content": "---- MODULE SpecMissingMost ----\nFoo == TRUE\n====\n",
            },
        ],
    )
    _write(source_summary, json.dumps({"kept_rows": 3}))
    _write_jsonl(
        candidates,
        [
            {
                "module": "SpecGood",
                "repo": "org/repo-a",
                "source_path": "SpecGood.tla",
                "content": "---- MODULE SpecGood ----\nVARIABLES vars\nInit == TRUE\nNext == TRUE\nSpec == Init /\\ [][Next]_vars\nTypeOK == TRUE\n====\n",
            }
        ],
    )
    _write(candidate_summary, json.dumps({"source_rows": 3, "kept_rows": 1}))

    report = build_report(
        source=source,
        source_summary=source_summary,
        candidates=candidates,
        candidate_summary=candidate_summary,
    )

    assert report["funnel"] == {
        "source_rows": 3,
        "shape_ready_rows": 1,
        "shape_ready_unique_modules": 1,
        "shape_ready_but_not_sany_clean_rows": 0,
        "sany_clean_rows": 1,
        "not_shape_ready_rows": 2,
    }
    assert report["missing_requirement_counts"]["operators"]["TypeOK"] == 2
    assert report["missing_requirement_counts"]["operators"]["Init"] == 1
    assert report["missing_requirement_counts"]["operators"]["Next"] == 1
    assert report["missing_requirement_counts"]["operators"]["Spec"] == 1
    assert report["missing_requirement_counts"]["vars_or_temporal_spec_shape"] == 1
    assert report["by_repo"]["repos"] == [
        {
            "repo": "org/repo-a",
            "total_rows": 2,
            "shape_ready_rows": 1,
            "sany_clean_rows": 1,
            "shape_ready_rate": 0.5,
            "sany_clean_rate": 0.5,
        },
        {
            "repo": "org/repo-b",
            "total_rows": 1,
            "shape_ready_rows": 0,
            "sany_clean_rows": 0,
            "shape_ready_rate": 0.0,
            "sany_clean_rate": 0.0,
        },
    ]
    assert report["warnings"] == []


def test_cli_writes_report_json(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source_summary = tmp_path / "source.summary.json"
    candidates = tmp_path / "candidates.jsonl"
    candidate_summary = tmp_path / "candidates.summary.json"
    out = tmp_path / "report.json"
    _write_jsonl(
        source,
        [
            {
                "module": "SpecGood",
                "repo": "org/repo-a",
                "source_path": "SpecGood.tla",
                "content": "---- MODULE SpecGood ----\nVARIABLES vars\nInit == TRUE\nNext == TRUE\nSpec == Init /\\ [][Next]_vars\nTypeOK == TRUE\n====\n",
            }
        ],
    )
    _write(source_summary, json.dumps({"kept_rows": 1}))
    _write_jsonl(candidates, [])
    _write(candidate_summary, json.dumps({"source_rows": 1, "kept_rows": 0}))
    script = Path(__file__).resolve().parents[1] / "scripts" / "inspect_ai4fm_public_seed_prover_funnel.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--source",
            str(source),
            "--source-summary",
            str(source_summary),
            "--candidates",
            str(candidates),
            "--candidate-summary",
            str(candidate_summary),
            "--out",
            str(out),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    stdout = json.loads(result.stdout)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert stdout["funnel"]["shape_ready_rows"] == 1
    assert stdout["funnel"]["sany_clean_rows"] == 0
    assert saved == stdout
