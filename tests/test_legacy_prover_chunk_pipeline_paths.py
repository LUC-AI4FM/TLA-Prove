from scripts import build_prover_sft, emit_prover_harmony, roundtrip_prover_sft


def test_legacy_prover_chunk_pipeline_stays_under_legacy_namespace() -> None:
    assert build_prover_sft.OUT.as_posix().endswith("data/processed/legacy_tla_prover_chunks/prover_chunks.jsonl")
    assert roundtrip_prover_sft.CHUNKS_IN == build_prover_sft.OUT
    assert roundtrip_prover_sft.OUT_VERIFIED.as_posix().endswith(
        "data/processed/legacy_tla_prover_chunks/prover_chunks_verified.jsonl"
    )
    assert roundtrip_prover_sft.OUT_FAILED.as_posix().endswith(
        "data/processed/legacy_tla_prover_chunks/prover_chunks_failed.jsonl"
    )
    assert emit_prover_harmony.IN == roundtrip_prover_sft.OUT_VERIFIED
    assert emit_prover_harmony.OUT_TRAIN.as_posix().endswith(
        "data/processed/legacy_tla_prover_chunks/prover_chunks_train.jsonl"
    )
    assert emit_prover_harmony.OUT_EVAL.as_posix().endswith(
        "data/processed/legacy_tla_prover_chunks/prover_chunks_eval.jsonl"
    )
    assert not emit_prover_harmony.OUT_EVAL.as_posix().endswith("data/processed/prover_eval.jsonl")
