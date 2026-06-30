import json
from pathlib import Path

from scripts.build_tla_prover_synthetic_repair_pairs import build_rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _record(prompt_id: str, final_spec: str, *, user_text: str = "Write a TLA+ spec.") -> dict:
    return {
        "_prompt_id": prompt_id,
        "messages": [
            {"role": "developer", "content": "You are ChatTLA."},
            {"role": "user", "content": user_text},
            {"role": "assistant", "channel": "final", "content": final_spec},
        ],
    }


def test_build_rows_emits_repair_pairs_and_summary(tmp_path: Path) -> None:
    gold = tmp_path / "gold.jsonl"
    _write_jsonl(
        gold,
        [
            _record(
                "alpha",
                (
                    "---- MODULE Alpha ----\n"
                    "EXTENDS Naturals\n\n"
                    "VARIABLES x\n\n"
                    "TypeOK == x \\in 0..3\n"
                    "Init == x = 0\n"
                    "Next == x' = x\n"
                    "Spec == Init /\\ [][Next]_<<x>>\n"
                    "====\n"
                ),
            ),
            _record(
                "beta",
                (
                    "---- MODULE Beta ----\n"
                    "VARIABLES y\n"
                    "Init == y = 1\n"
                    "Next == y' = y\n"
                    "Spec == Init /\\ [][Next]_<<y>>\n"
                    "====\n"
                ),
                user_text="Model a stable counter.",
            ),
        ],
    )

    rows, summary = build_rows(gold)

    assert len(rows) == 2
    assert summary["rows"] == 2
    assert summary["source_rows"] == 2
    assert summary["skipped_rows"] == 0
    assert sum(summary["difficulty_counts"].values()) == 2
    assert sum(summary["mutation_counts"].values()) == 2
    for row in rows:
        assert row["repair_id"].startswith(("alpha::", "beta::"))
        assert "::synthetic::" in row["repair_id"]
        assert row["after_score"] == 1.0
        assert row["difficulty"] in {"easy", "medium", "hard"}
        assert row["mutation"]
        assert row["errors_rendered"]
        assert row["repaired_spec"].startswith("---- MODULE ")
        assert row["broken_spec"] != row["repaired_spec"]


def test_build_rows_skips_non_module_outputs(tmp_path: Path) -> None:
    gold = tmp_path / "gold.jsonl"
    _write_jsonl(
        gold,
        [
            _record("good", "---- MODULE Good ----\nVARIABLES x\nInit == x = 0\nNext == x' = x\n====\n"),
            {"_prompt_id": "bad", "messages": [{"role": "user", "content": "not enough"}]},
            _record("not-module", "This is not a TLA+ module."),
        ],
    )

    rows, summary = build_rows(gold)

    assert len(rows) == 1
    assert rows[0]["repair_id"].startswith("good::")
    assert "::synthetic::" in rows[0]["repair_id"]
    assert summary["source_rows"] == 3
    assert summary["skipped_rows"] == 2
