from pathlib import Path


def test_diagnose_prover_scripts_fallback_to_current_eval_corpus_when_legacy_train_is_missing() -> None:
    repo = Path(__file__).resolve().parents[1]
    diag1 = (repo / "scripts" / "diagnose_prover.py").read_text(encoding="utf-8")
    diag2 = (repo / "scripts" / "diagnose_prover2.py").read_text(encoding="utf-8")

    for text in (diag1, diag2):
        assert 'FALLBACK_TRAINLIKE_JSONL = REPO / "data" / "processed" / "prover_eval.jsonl"' in text
        assert 'TRAIN_JSONL if TRAIN_JSONL.exists() else FALLBACK_TRAINLIKE_JSONL' in text
