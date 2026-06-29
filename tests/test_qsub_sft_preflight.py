from pathlib import Path


PBS = Path(__file__).resolve().parents[1] / "scripts" / "qsub_sophia_tla_prover_sft_preflight.pbs"


def test_sft_preflight_uses_new_prover_corpus_and_safe_bounds() -> None:
    text = PBS.read_text(encoding="utf-8")

    assert "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl" in text
    assert "data/processed/formalllm_eval_v1.jsonl" in text
    assert "src.training.train" in text
    assert "--prover" in text
    assert "--eval-file \"$PROVER_EVAL_FILE\"" in text
    assert "--max-steps 3" in text
    assert "--max-length 2048" in text
    assert "--per-device-batch-size 1" in text
    assert "--max-gpu-memory-mb 36000" in text
    assert "CHATTLA_BASE_MODEL" in text
    assert "EricSpencer00/chattla-20b" in text
    assert "HF_HUB_OFFLINE=1" in text
    assert "MLFLOW_TRACKING_URI" in text
    assert "MLFLOW_ALLOW_FILE_STORE" in text
    assert "startup/data/VRAM/full-FormaLLM preflight" in text
