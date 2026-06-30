from pathlib import Path

from scripts.train_tla_prover_local import build_run_plan


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_run_plan_defaults_to_baseline_prover_corpus_and_output_dir(tmp_path: Path) -> None:
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl")
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        '{"lanes":{"default":{"rows":1330,"default_publish_lane":true,"intended_role":"current_publish_baseline","trainable":true}}}\n',
    )

    plan = build_run_plan(
        repo=tmp_path,
        requested_corpus=None,
        output_dir=None,
        experiment_name=None,
        extra_args=[],
    )

    assert plan["resolved_corpus"]["alias"] == "default"
    assert plan["output_dir"].endswith("outputs/checkpoints_prover")
    assert plan["experiment_name"] == "ChatTLA-Prover-gpt-oss-20b"
    assert plan["command"][:6] == [
        "python3",
        "-m",
        "src.training.train",
        "--prover",
        "--sft-corpus",
        "default",
    ]


def test_build_run_plan_uses_named_expanded_lane_specific_output_dir(tmp_path: Path) -> None:
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl")
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        '{"lanes":{"expanded":{"rows":2503,"default_publish_lane":false,"intended_role":"bounded_public_comparison_train","trainable":true}}}\n',
    )

    plan = build_run_plan(
        repo=tmp_path,
        requested_corpus="expanded",
        output_dir=None,
        experiment_name=None,
        extra_args=["--smoke-test"],
    )

    assert plan["resolved_corpus"]["alias"] == "expanded"
    assert plan["output_dir"].endswith("outputs/checkpoints_prover_expanded")
    assert plan["experiment_name"] == "ChatTLA-Prover-gpt-oss-20b-expanded"
    assert "--sft-corpus" in plan["command"]
    assert "expanded" in plan["command"]
    assert plan["command"][-1] == "--smoke-test"


def test_build_run_plan_uses_train_file_for_custom_path(tmp_path: Path) -> None:
    custom = tmp_path / "data/custom/train.jsonl"
    _write(custom)

    plan = build_run_plan(
        repo=tmp_path,
        requested_corpus="data/custom/train.jsonl",
        output_dir=None,
        experiment_name=None,
        extra_args=[],
    )

    assert plan["resolved_corpus"]["alias"] is None
    assert "--train-file" in plan["command"]
    assert str(custom) in plan["command"]
    assert plan["output_dir"].endswith("outputs/checkpoints_prover_data-custom-train-jsonl")
