import json
from pathlib import Path

from scripts.build_tla_prover_repair_corpus import build_corpus


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _row(repair_id: str, before_score: float) -> dict:
    return {
        "repair_id": repair_id,
        "nl": f"nl {repair_id}",
        "broken_spec": "---- MODULE Broken ----\n====",
        "errors_rendered": "diag",
        "verify_summary": "summary",
        "before_score": before_score,
        "repaired_spec": "---- MODULE Fixed ----\n====",
        "after_score": 1.0,
    }


def test_build_corpus_merges_sources_and_preserves_source_counts(tmp_path: Path) -> None:
    ralph = tmp_path / "ralph.jsonl"
    bench = tmp_path / "bench.jsonl"
    _write_jsonl(ralph, [_row("R1", 0.05), _row("R2", 0.45)])
    _write_jsonl(bench, [_row("B1", 0.15), _row("R2", 0.45)])

    rows, summary = build_corpus(repair_pair_files=[ralph, bench], repo=tmp_path)

    assert [row["repair_id"] for row in rows] == ["R1", "B1", "R2"]
    assert rows[0]["source_file"] == "ralph.jsonl"
    assert rows[1]["source_file"] == "bench.jsonl"
    assert summary["rows"] == 3
    assert summary["source_rows"] == {"ralph.jsonl": 2, "bench.jsonl": 2}
    assert summary["kept_rows_by_source"] == {"ralph.jsonl": 2, "bench.jsonl": 1}
    assert summary["duplicate_repair_ids"] == ["R2"]
    assert summary["difficulty_counts"] == {"easy": 1, "medium": 1, "hard": 1}
    assert summary["health"]["ok"] is True
    assert summary["health"]["warnings"] == []


def test_build_corpus_reports_missing_sources_without_failing(tmp_path: Path) -> None:
    bench = tmp_path / "bench.jsonl"
    _write_jsonl(bench, [_row("B1", 0.15)])

    rows, summary = build_corpus(
        repair_pair_files=[tmp_path / "missing.jsonl", bench],
        repo=tmp_path,
    )

    assert [row["repair_id"] for row in rows] == ["B1"]
    assert summary["missing_sources"] == ["missing.jsonl"]
    assert summary["kept_rows_by_source"] == {"bench.jsonl": 1}


def test_build_corpus_prefers_available_long_ralph_source(tmp_path: Path) -> None:
    long_ralph = tmp_path / "data/processed/ralph_repair_pairs_long_latest.jsonl"
    benchmark = tmp_path / "data/processed/benchmark_repair_pairs_fc128best.jsonl"
    _write_jsonl(long_ralph, [_row("LR1", 0.35)])
    _write_jsonl(benchmark, [_row("B1", 0.15)])

    rows, summary = build_corpus(
        repair_pair_files=[
            tmp_path / "data/processed/ralph_repair_pairs.jsonl",
            long_ralph,
            benchmark,
        ],
        repo=tmp_path,
    )

    assert [row["repair_id"] for row in rows] == ["B1", "LR1"]
    assert summary["missing_sources"] == ["data/processed/ralph_repair_pairs.jsonl"]
    assert summary["kept_rows_by_source"] == {
        "data/processed/ralph_repair_pairs_long_latest.jsonl": 1,
        "data/processed/benchmark_repair_pairs_fc128best.jsonl": 1,
    }


def test_build_corpus_treats_synthetic_pairs_as_valid_non_benchmark_fallback(tmp_path: Path) -> None:
    synthetic = tmp_path / "data/processed/tla_prover_synthetic_repair_pairs_v1.jsonl"
    benchmark = tmp_path / "data/processed/benchmark_repair_pairs_fc128best.jsonl"
    _write_jsonl(synthetic, [_row("S1", 0.25), _row("S2", 0.45)])
    _write_jsonl(benchmark, [_row("B1", 0.05)])

    rows, summary = build_corpus(
        repair_pair_files=[
            tmp_path / "data/processed/ralph_repair_pairs.jsonl",
            tmp_path / "data/processed/ralph_repair_pairs_long_latest.jsonl",
            synthetic,
            benchmark,
        ],
        repo=tmp_path,
    )

    assert [row["repair_id"] for row in rows] == ["B1", "S1", "S2"]
    assert summary["health"]["ok"] is True
    assert summary["health"]["warnings"] == []
    assert summary["health"]["benchmark_only"] is False
    assert summary["health"]["only_easy_rows"] is False
    assert summary["missing_sources"] == [
        "data/processed/ralph_repair_pairs.jsonl",
        "data/processed/ralph_repair_pairs_long_latest.jsonl",
    ]
    assert summary["kept_rows_by_source"] == {
        "data/processed/tla_prover_synthetic_repair_pairs_v1.jsonl": 2,
        "data/processed/benchmark_repair_pairs_fc128best.jsonl": 1,
    }


def test_build_corpus_flags_degraded_benchmark_only_easy_mix(tmp_path: Path) -> None:
    benchmark = tmp_path / "data/processed/benchmark_repair_pairs_fc128best.jsonl"
    _write_jsonl(benchmark, [_row("B1", 0.01), _row("B2", 0.05)])

    _rows, summary = build_corpus(
        repair_pair_files=[
            tmp_path / "data/processed/ralph_repair_pairs.jsonl",
            tmp_path / "data/processed/ralph_repair_pairs_long_latest.jsonl",
            benchmark,
        ],
        repo=tmp_path,
    )

    assert summary["health"]["ok"] is False
    assert summary["health"]["benchmark_only"] is True
    assert summary["health"]["only_easy_rows"] is True
    assert "missing_ralph_sources" in summary["health"]["warnings"]
    assert "single_source_repair_corpus" in summary["health"]["warnings"]
    assert "easy_only_repair_corpus" in summary["health"]["warnings"]
