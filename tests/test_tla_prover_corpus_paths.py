from pathlib import Path

from scripts.tla_prover_corpus_paths import (
    DEFAULT_LOCAL_SFT_TRAIN,
    DEFAULT_PROBE_FALLBACK,
    DEFAULT_PUBLIC_SFT_TRAIN,
    DEFAULT_TRAINLIKE_PROBE_SOURCE,
    FULL_PUBLIC_LOCAL_SFT_TRAIN,
    SHAPE_READY_LOCAL_SFT_TRAIN,
    SHAPE_READY_NOT_SANY_LOCAL_SFT_TRAIN,
    infer_named_sft_alias,
    resolve_named_sft_corpus,
    resolve_remote_sft_corpus_metadata,
    resolve_probe_corpus_file,
    resolve_remote_sft_train_file,
    summary_path_for_sft_train_file,
)


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_resolve_remote_sft_train_file_prefers_local_generated_corpus(tmp_path: Path) -> None:
    _write(tmp_path / DEFAULT_LOCAL_SFT_TRAIN)
    _write(tmp_path / DEFAULT_PUBLIC_SFT_TRAIN)

    resolved, checked = resolve_remote_sft_train_file(tmp_path)

    assert resolved == DEFAULT_LOCAL_SFT_TRAIN
    assert checked == [DEFAULT_LOCAL_SFT_TRAIN, DEFAULT_PUBLIC_SFT_TRAIN]


def test_resolve_remote_sft_train_file_falls_back_to_public_bundle_copy(tmp_path: Path) -> None:
    _write(tmp_path / DEFAULT_PUBLIC_SFT_TRAIN)

    resolved, checked = resolve_remote_sft_train_file(tmp_path)

    assert resolved == DEFAULT_PUBLIC_SFT_TRAIN
    assert checked == [DEFAULT_LOCAL_SFT_TRAIN, DEFAULT_PUBLIC_SFT_TRAIN]


def test_resolve_named_sft_corpus_supports_public_aliases() -> None:
    assert resolve_named_sft_corpus("default") is None
    assert resolve_named_sft_corpus("expanded") == "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl"
    assert resolve_named_sft_corpus("full-public") == FULL_PUBLIC_LOCAL_SFT_TRAIN
    assert resolve_named_sft_corpus("shape-ready") == SHAPE_READY_LOCAL_SFT_TRAIN
    assert (
        resolve_named_sft_corpus("shape-ready-not-sany")
        == SHAPE_READY_NOT_SANY_LOCAL_SFT_TRAIN
    )
    assert resolve_named_sft_corpus("data/custom.jsonl") == "data/custom.jsonl"


def test_summary_path_and_alias_resolution_cover_default_and_public_lanes() -> None:
    assert infer_named_sft_alias(DEFAULT_LOCAL_SFT_TRAIN) == "default"
    assert infer_named_sft_alias(DEFAULT_PUBLIC_SFT_TRAIN) == "default"
    assert infer_named_sft_alias(FULL_PUBLIC_LOCAL_SFT_TRAIN) == "full-public"
    assert summary_path_for_sft_train_file(DEFAULT_LOCAL_SFT_TRAIN) == (
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json"
    )
    assert summary_path_for_sft_train_file(FULL_PUBLIC_LOCAL_SFT_TRAIN) == (
        "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json"
    )


def test_resolve_remote_sft_train_file_accepts_named_full_public_alias(tmp_path: Path) -> None:
    _write(tmp_path / FULL_PUBLIC_LOCAL_SFT_TRAIN)

    resolved, checked = resolve_remote_sft_train_file(tmp_path, requested="full-public")

    assert resolved == FULL_PUBLIC_LOCAL_SFT_TRAIN
    assert checked == [FULL_PUBLIC_LOCAL_SFT_TRAIN]


def test_resolve_remote_sft_corpus_metadata_reads_lane_details_from_matrix(tmp_path: Path) -> None:
    _write(tmp_path / FULL_PUBLIC_LOCAL_SFT_TRAIN)
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        (
            '{"lanes":{"full-public":{"rows":2508,"default_publish_lane":false,'
            '"intended_role":"maximal_committed_public_comparison_train","trainable":true}}}\n'
        ),
    )

    metadata = resolve_remote_sft_corpus_metadata(tmp_path, requested="full-public")

    assert metadata["alias"] == "full-public"
    assert metadata["resolved_train_file"] == FULL_PUBLIC_LOCAL_SFT_TRAIN
    assert metadata["rows"] == 2508
    assert metadata["default_publish_lane"] is False
    assert metadata["intended_role"] == "maximal_committed_public_comparison_train"
    assert metadata["experiment_matrix_lane_found"] is True


def test_resolve_probe_corpus_file_marks_eval_probe_fallback_when_legacy_train_is_missing(tmp_path: Path) -> None:
    _write(tmp_path / DEFAULT_PROBE_FALLBACK)

    resolved, used_fallback = resolve_probe_corpus_file(tmp_path)

    assert resolved == DEFAULT_PROBE_FALLBACK
    assert used_fallback is True


def test_resolve_probe_corpus_file_uses_legacy_train_when_present(tmp_path: Path) -> None:
    _write(tmp_path / DEFAULT_TRAINLIKE_PROBE_SOURCE)
    _write(tmp_path / DEFAULT_PROBE_FALLBACK)

    resolved, used_fallback = resolve_probe_corpus_file(tmp_path)

    assert resolved == DEFAULT_TRAINLIKE_PROBE_SOURCE
    assert used_fallback is False
