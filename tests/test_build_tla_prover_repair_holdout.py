import json
from pathlib import Path

from scripts.build_tla_prover_repair_holdout import build_holdout


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_holdout_is_validated_minus_train(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    validated = tmp_path / "validated.jsonl"
    _write_jsonl(train, [{"repair_id": "a"}, {"repair_id": "b"}])
    _write_jsonl(validated, [{"repair_id": "a"}, {"repair_id": "c"}, {"repair_id": "d"}])

    holdout, summary = build_holdout(train, validated)

    assert [r["repair_id"] for r in holdout] == ["c", "d"]
    assert summary["ok"] is True
    assert summary["train_overlap"] == []
    assert summary["holdout_rows"] == 2


def test_empty_holdout_fails_the_gate(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    validated = tmp_path / "validated.jsonl"
    _write_jsonl(train, [{"repair_id": "a"}])
    _write_jsonl(validated, [{"repair_id": "a"}])

    holdout, summary = build_holdout(train, validated)

    assert holdout == []
    assert summary["ok"] is False


def test_real_corpora_are_disjoint() -> None:
    from scripts.build_tla_prover_repair_holdout import DEFAULT_TRAIN, DEFAULT_VALIDATED

    holdout, summary = build_holdout(DEFAULT_TRAIN, DEFAULT_VALIDATED)

    assert summary["ok"] is True
    assert summary["train_overlap"] == []
    assert summary["holdout_rows"] >= 7
