from pathlib import Path


def test_diagnose_prover_scripts_use_shared_probe_corpus_helper() -> None:
    repo = Path(__file__).resolve().parents[1]
    diag1 = (repo / "scripts" / "diagnose_prover.py").read_text(encoding="utf-8")
    diag2 = (repo / "scripts" / "diagnose_prover2.py").read_text(encoding="utf-8")

    for text in (diag1, diag2):
        assert "from scripts.tla_prover_corpus_paths import resolve_probe_corpus_file" in text
        assert "train_path, using_probe_fallback = resolve_probe_corpus_file(REPO)" in text
        assert "training-like probe corpus" in text
