import json
from pathlib import Path

from scripts.build_sany_tlc_eval_corpus import build_rows
from src.validators.tlc_validator import validate_string


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_rows_uses_verified_holdout_rows(tmp_path: Path) -> None:
    source = tmp_path / "holdout.jsonl"
    _write(
        source,
        [
            {
                "module": "HoldoutA",
                "topic_desc": "A held-out protocol.",
                "spec": "---- MODULE HoldoutA ----\nTypeOK == TRUE\n====\n",
                "is_diamond": True,
                "sany_pass": True,
                "tier": "gold",
                "mutation_caught": True,
                "trivial_invariant": False,
                "distinct_states": 2,
                "invariants_checked": 1,
                "batch": "test",
            }
        ],
    )

    rows, summary = build_rows(source)

    assert summary["source_rows"] == 1
    assert summary["kept_rows"] == 1
    row = rows[0]
    assert row["_tier"] == "sany_tlc_pass_eval"
    assert row["_source"] == "diamond_eval_holdout_verified"
    assert row["_module"] == "HoldoutA"
    assert "SPECIFICATION Spec" in row["messages"][-1]["content"]
    assert "INVARIANT TypeOK" in row["messages"][-1]["content"]


def test_checked_in_sany_tlc_eval_matches_builder_output() -> None:
    repo = Path(__file__).resolve().parents[1]
    out = repo / "data/processed/sany_tlc_pass_eval_v1.jsonl"
    rows, _summary = build_rows(repo / "data/processed/diamond_eval_holdout.jsonl")

    assert out.exists()
    checked_in = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert checked_in == rows
    assert len(checked_in) == 30


def test_chain_replication_holdout_replays_without_deadlock() -> None:
    repo = Path(__file__).resolve().parents[1]
    rows, _summary = build_rows(repo / "data/processed/diamond_eval_holdout.jsonl")
    chain = next(row for row in rows if row["_module"] == "ChainReplication")
    final = chain["messages"][-1]["content"]

    validation = validate_string(final, module_name="ChainReplication", timeout=10)

    assert validation.tier == "gold"
    assert validation.semantic.distinct_states > 0
    assert not validation.tlc_violations
