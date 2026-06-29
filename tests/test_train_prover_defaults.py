from pathlib import Path


def test_train_prover_defaults_point_at_current_mixed_corpus() -> None:
    train_py = (Path(__file__).resolve().parents[1] / "src" / "training" / "train.py").read_text(encoding="utf-8")

    assert '"tla_prover" / "chattla_tla_prover_sft_v1.jsonl"' in train_py
    assert "read chattla_tla_prover_sft_v1.jsonl/prover_eval.jsonl by default" in train_py
    assert "chattla_tla_prover_sft_public_expanded_v1.jsonl" in train_py
    assert "--train-file data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl" in train_py
