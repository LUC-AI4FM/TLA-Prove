import hashlib
import json
from pathlib import Path

from scripts.build_sany_tlc_pass_corpus import DEFAULT_HOLDOUT, DEFAULT_OUT, DEFAULT_SOURCE, build_rows, write_outputs


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _diamond(module: str, **overrides: object) -> dict:
    row = {
        "module": module,
        "topic_desc": f"Build {module}.",
        "spec": f"---- MODULE {module} ----\n====\n",
        "is_diamond": True,
        "sany_pass": True,
        "tier": "gold",
        "mutation_caught": True,
        "trivial_invariant": False,
        "distinct_states": 3,
        "invariants_checked": 1,
    }
    row.update(overrides)
    return row


def test_build_rows_keeps_only_verified_sany_tlc_passes_and_excludes_holdout(tmp_path: Path) -> None:
    source = tmp_path / "diamond.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write_jsonl(
        source,
        [
            _diamond("TrainMe"),
            _diamond("Holdout"),
            _diamond("NotDiamond", is_diamond=False),
            _diamond("NoSany", sany_pass=False),
            _diamond("Trivial", trivial_invariant=True),
        ],
    )
    _write_jsonl(holdout, [_diamond("Holdout")])

    rows, summary = build_rows(source, holdout)

    assert summary["source_rows"] == 5
    assert summary["holdout_modules"] == 1
    assert summary["kept_rows"] == 1
    assert summary["skipped_holdout"] == 1
    assert rows[0]["_tier"] == "sany_tlc_pass"
    assert rows[0]["_module"] == "TrainMe"
    assert rows[0]["_evidence"]["sany_pass"] is True
    assert rows[0]["messages"][-1]["content"].startswith("---- MODULE TrainMe ----")
    assert "SPECIFICATION Spec" in rows[0]["messages"][-1]["content"]


def test_build_rows_appends_typeok_invariant_when_defined(tmp_path: Path) -> None:
    source = tmp_path / "diamond.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write_jsonl(
        source,
        [
            _diamond(
                "HasTypeOK",
                spec="---- MODULE HasTypeOK ----\nEXTENDS Naturals\nTypeOK == TRUE\n====\n",
            )
        ],
    )
    _write_jsonl(holdout, [])

    rows, _summary = build_rows(source, holdout)
    final = rows[0]["messages"][-1]["content"]

    assert "SPECIFICATION Spec" in final
    assert "INVARIANT TypeOK" in final


def test_build_rows_appends_constant_assignments_when_declared(tmp_path: Path) -> None:
    source = tmp_path / "diamond.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write_jsonl(
        source,
        [
            _diamond(
                "HasConstants",
                spec=(
                    "---- MODULE HasConstants ----\n"
                    "EXTENDS Naturals\n"
                    "CONSTANTS N, Procs\n"
                    "VARIABLE x\n"
                    "vars == <<x>>\n"
                    "Init == x = 0\n"
                    "Next == UNCHANGED x\n"
                    "Spec == Init /\\ [][Next]_vars\n"
                    "TypeOK == /\\ x \\in 0..N /\\ Procs # {}\n"
                    "====\n"
                ),
            )
        ],
    )
    _write_jsonl(holdout, [])

    rows, _summary = build_rows(source, holdout)
    final = rows[0]["messages"][-1]["content"]

    assert "CONSTANT N = 3" in final
    assert "CONSTANT Procs = {v1, v2, v3}" in final


def test_build_rows_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "diamond.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    _write_jsonl(source, [_diamond("B"), _diamond("A")])
    _write_jsonl(holdout, [])

    rows_a, summary_a = build_rows(source, holdout)
    rows_b, summary_b = build_rows(source, holdout)

    assert rows_a == rows_b
    assert summary_a == summary_b
    assert [row["_module"] for row in rows_a] == ["A", "B"]


def test_write_outputs_uses_repo_relative_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    out = repo / "data/processed/sany_tlc_pass_sft_v1.test.jsonl"
    rows = [{"messages": [{"role": "assistant", "channel": "final", "content": "---- MODULE A ----\n====\n"}]}]
    summary = {"source": "outputs/diamond_gen/diamond_generated.jsonl", "holdout": "data/processed/diamond_eval_holdout.jsonl"}

    try:
        final_summary = write_outputs(rows, summary, out)
        assert final_summary["out"] == "data/processed/sany_tlc_pass_sft_v1.test.jsonl"
        assert final_summary["summary"] == "data/processed/sany_tlc_pass_sft_v1.test.summary.json"
    finally:
        out.unlink(missing_ok=True)
        out.with_suffix(".summary.json").unlink(missing_ok=True)


def test_checked_in_sany_tlc_artifact_matches_builder_output() -> None:
    rows, summary = build_rows(DEFAULT_SOURCE, DEFAULT_HOLDOUT)
    serialized = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    summary_path = DEFAULT_OUT.with_suffix(".summary.json")
    checked_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert DEFAULT_OUT.read_text(encoding="utf-8") == serialized
    assert checked_summary["kept_rows"] == summary["kept_rows"] == len(rows)
    assert checked_summary["jsonl_sha256"] == hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    for row in rows:
        final = row["messages"][-1]["content"]
        assert "SPECIFICATION Spec" in final
        if "TypeOK ==" in final:
            assert "INVARIANT TypeOK" in final
