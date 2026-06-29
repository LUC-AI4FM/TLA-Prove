import json
from pathlib import Path

from scripts.build_tla_prover_finetune_corpus import build_corpus, normalize_messages, write_outputs


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_corpus_preserves_base_and_oversamples_verified_rows(tmp_path: Path) -> None:
    base = tmp_path / "base.jsonl"
    formalllm = tmp_path / "formalllm.jsonl"
    verified = tmp_path / "verified.jsonl"
    _write_jsonl(base, [{"_source": "base", "messages": [{"role": "user", "content": "base"}]}])
    _write_jsonl(formalllm, [{"_source": "formalllm", "messages": [{"role": "user", "content": "fm"}]}])
    _write_jsonl(
        verified,
        [
            {
                "module": "Mini",
                "verifier": "TLAPS 1.5.0 --threads 1",
                "source_artifact": "proofs.tar.gz",
                "messages": [{"role": "assistant", "content": "proof"}],
            }
        ],
    )

    rows, summary = build_corpus(base, formalllm, verified, tlaps_weight=3, seed=7)

    assert summary["base_rows"] == 1
    assert summary["formalllm_rows"] == 1
    assert summary["verified_tlaps_rows"] == 1
    assert summary["verified_tlaps_weight"] == 3
    assert summary["total_rows"] == 5
    assert sum(1 for row in rows if row.get("_tier") == "verified_tlaps_proof") == 3
    assert all(row["messages"] for row in rows)


def test_build_corpus_is_deterministic(tmp_path: Path) -> None:
    base = tmp_path / "base.jsonl"
    formalllm = tmp_path / "formalllm.jsonl"
    verified = tmp_path / "verified.jsonl"
    _write_jsonl(base, [{"messages": [{"role": "user", "content": str(i)}]} for i in range(3)])
    _write_jsonl(formalllm, [{"messages": [{"role": "user", "content": "fm"}]}])
    _write_jsonl(verified, [{"module": "M", "messages": [{"role": "assistant", "content": "proof"}]}])

    rows_a, summary_a = build_corpus(base, formalllm, verified, tlaps_weight=2, seed=123)
    rows_b, summary_b = build_corpus(base, formalllm, verified, tlaps_weight=2, seed=123)

    assert rows_a == rows_b
    assert summary_a == summary_b


def test_build_corpus_summary_uses_repo_relative_paths(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    out = repo / "data/processed/tla_prover/chattla_tla_prover_sft_v1.test.jsonl"
    rows = [{"messages": [{"role": "user", "content": "x"}]}]
    summary = {
        "base": "data/processed/diamond_sft_v3.jsonl",
        "formalllm": "data/processed/formalllm_eval_v1.jsonl",
        "verified_tlaps": "data/processed/tla_prover/verified_tlaps_sft_seed.jsonl",
        "base_rows": 1,
        "formalllm_rows": 1,
        "verified_tlaps_rows": 1,
        "verified_tlaps_weight": 1,
        "total_rows": 3,
        "seed": 1,
    }

    try:
        final_summary = write_outputs(rows, summary, out)
        assert final_summary["out"] == "data/processed/tla_prover/chattla_tla_prover_sft_v1.test.jsonl"
        assert final_summary["summary"] == "data/processed/tla_prover/chattla_tla_prover_sft_v1.test.summary.json"
    finally:
        out.unlink(missing_ok=True)
        out.with_suffix(".summary.json").unlink(missing_ok=True)


def test_normalize_messages_converts_system_and_adds_assistant_channels() -> None:
    messages = [
        {"role": "system", "content": "dev"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "analysis"},
        {"role": "assistant", "content": "final"},
    ]

    normalized = normalize_messages(messages)

    assert normalized[0]["role"] == "developer"
    assert normalized[2]["channel"] == "analysis"
    assert normalized[3]["channel"] == "final"
