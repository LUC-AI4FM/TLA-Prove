from pathlib import Path

from src.training.prover_corpus_selection import resolve_local_prover_train_selection


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_resolve_local_prover_train_selection_defaults_to_local_baseline(tmp_path: Path) -> None:
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl")
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        '{"lanes":{"default":{"rows":1330,"default_publish_lane":true,"intended_role":"current_publish_baseline","trainable":true}}}\n',
    )

    selection = resolve_local_prover_train_selection(tmp_path, requested=None)

    assert selection["train_path"] == (
        tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl"
    )
    assert selection["metadata"]["alias"] == "default"
    assert selection["metadata"]["rows"] == 1330


def test_resolve_local_prover_train_selection_accepts_named_full_public_alias(tmp_path: Path) -> None:
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl")
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        '{"lanes":{"full-public":{"rows":2508,"default_publish_lane":false,"intended_role":"maximal_committed_public_comparison_train","trainable":true}}}\n',
    )

    selection = resolve_local_prover_train_selection(tmp_path, requested="full-public")

    assert selection["train_path"] == (
        tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl"
    )
    assert selection["metadata"]["alias"] == "full-public"
    assert selection["metadata"]["rows"] == 2508


def test_resolve_local_prover_train_selection_passes_through_custom_path(tmp_path: Path) -> None:
    custom = tmp_path / "data/custom/train.jsonl"
    _write(custom)

    selection = resolve_local_prover_train_selection(tmp_path, requested="data/custom/train.jsonl")

    assert selection["train_path"] == custom
    assert selection["metadata"]["requested_path"] == "data/custom/train.jsonl"
