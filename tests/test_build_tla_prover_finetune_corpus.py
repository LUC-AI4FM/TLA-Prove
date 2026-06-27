import json
from pathlib import Path

from scripts.build_tla_prover_finetune_corpus import build_corpus, normalize_messages


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_corpus_preserves_base_and_oversamples_verified_rows(tmp_path: Path) -> None:
    base = tmp_path / "base.jsonl"
    verified = tmp_path / "verified.jsonl"
    _write_jsonl(base, [{"_source": "base", "messages": [{"role": "user", "content": "base"}]}])
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

    rows, summary = build_corpus(base, verified, tlaps_weight=3, seed=7)

    assert summary["base_rows"] == 1
    assert summary["verified_tlaps_rows"] == 1
    assert summary["verified_tlaps_weight"] == 3
    assert summary["total_rows"] == 4
    assert sum(1 for row in rows if row.get("_tier") == "verified_tlaps_proof") == 3
    assert all(row["messages"] for row in rows)


def test_build_corpus_is_deterministic(tmp_path: Path) -> None:
    base = tmp_path / "base.jsonl"
    verified = tmp_path / "verified.jsonl"
    _write_jsonl(base, [{"messages": [{"role": "user", "content": str(i)}]} for i in range(3)])
    _write_jsonl(verified, [{"module": "M", "messages": [{"role": "assistant", "content": "proof"}]}])

    rows_a, summary_a = build_corpus(base, verified, tlaps_weight=2, seed=123)
    rows_b, summary_b = build_corpus(base, verified, tlaps_weight=2, seed=123)

    assert rows_a == rows_b
    assert summary_a == summary_b


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
