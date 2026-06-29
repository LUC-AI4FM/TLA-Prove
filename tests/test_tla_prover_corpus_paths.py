from pathlib import Path

from scripts.tla_prover_corpus_paths import (
    DEFAULT_LOCAL_SFT_TRAIN,
    DEFAULT_PROBE_FALLBACK,
    DEFAULT_PUBLIC_SFT_TRAIN,
    DEFAULT_TRAINLIKE_PROBE_SOURCE,
    resolve_probe_corpus_file,
    resolve_remote_sft_train_file,
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
