import csv
import json
from pathlib import Path

from scripts.build_benchmark_repair_pairs import build_pairs


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_build_pairs_emits_flattened_repair_rows_with_gold_targets(tmp_path: Path) -> None:
    bench_suite = tmp_path / "data/benchmarks/benchmark_suite.json"
    _write(
        bench_suite,
        json.dumps(
            [
                {
                    "id": "BM001",
                    "name": "Mutual Exclusion",
                    "description": "Write a mutual exclusion spec.",
                    "hints": "Bound the process domain.",
                },
                {
                    "id": "BM002",
                    "name": "Queue",
                    "description": "Write a queue spec.",
                },
            ]
        ),
    )
    failed_csv = tmp_path / "outputs/benchmark_results/benchmark_results_fc128best_full.csv"
    _write_csv(
        failed_csv,
        [
            {
                "model": "chattla:20b-fc128best",
                "benchmark_id": "BM001",
                "name": "Mutual Exclusion",
                "domain": "sched",
                "difficulty": 2,
                "sany_pass": 0,
                "tlc_pass": 0,
                "structural_score": 0.85,
                "tlc_tier": "bronze",
                "runtime_s": 31.0,
                "generated_spec": "---- MODULE Mutex ----\nVARIABLES x, x\nNext == ...\n====",
                "init_present": 0,
                "next_present": 0,
                "init_level_ok": 0,
                "next_level_ok": 0,
                "invariants_declared": 0,
                "tlc_depth1_ok": 0,
                "partial_credit": 0.0,
                "expected_invariant_overlap": 0,
                "plan_used": 0,
            },
            {
                "model": "chattla:20b-fc128best",
                "benchmark_id": "BM002",
                "name": "Queue",
                "domain": "storage",
                "difficulty": 2,
                "sany_pass": 1,
                "tlc_pass": 1,
                "structural_score": 1.0,
                "tlc_tier": "gold",
                "runtime_s": 20.0,
                "generated_spec": "---- MODULE Queue ----\nVARIABLES q\nInit == q = <<>>\nNext == UNCHANGED q\nSpec == Init /\\ [][Next]_<<q>>\n====",
                "init_present": 1,
                "next_present": 1,
                "init_level_ok": 1,
                "next_level_ok": 1,
                "invariants_declared": 1,
                "tlc_depth1_ok": 1,
                "partial_credit": 1.0,
                "expected_invariant_overlap": 1,
                "plan_used": 1,
            },
        ],
    )
    gold_csv = tmp_path / "outputs/benchmark_results/benchmark_results_gold_full.csv"
    _write_csv(
        gold_csv,
        [
            {
                "model": "chattla:20b-repair",
                "benchmark_id": "BM001",
                "name": "Mutual Exclusion",
                "domain": "sched",
                "difficulty": 2,
                "sany_pass": 1,
                "tlc_pass": 1,
                "structural_score": 0.95,
                "tlc_tier": "gold",
                "runtime_s": 18.0,
                "generated_spec": "---- MODULE MutualExclusion ----\nVARIABLES state\nInit == state = 0\nNext == state' = state\nTypeOK == state \\in 0..1\nSpec == Init /\\ [][Next]_<<state>>\n====",
                "init_present": 1,
                "next_present": 1,
                "init_level_ok": 1,
                "next_level_ok": 1,
                "invariants_declared": 1,
                "tlc_depth1_ok": 1,
                "partial_credit": 1.0,
                "expected_invariant_overlap": 1,
                "plan_used": 1,
            }
        ],
    )

    rows, summary = build_pairs(
        benchmark_suite_path=bench_suite,
        benchmark_to_module_path=tmp_path / "data/benchmarks/missing_benchmark_to_module.json",
        failed_csv_path=failed_csv,
        benchmark_dirs=(failed_csv.parent,),
        public_candidates_path=tmp_path / "data/processed/missing_public_candidates.jsonl",
        benchmark_model="chattla:20b-fc128best",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["repair_id"] == "BM001::chattla_20b_fc128best"
    assert "Bound the process domain." in row["nl"]
    assert row["before_score"] == 0.0
    assert row["after_score"] == 1.0
    assert row["repaired_spec"].startswith("---- MODULE MutualExclusion ----")
    assert "missing core components: Init, Next, Init-level, Next-level, invariants, TLC depth-1" in row["errors_rendered"]
    assert "red flags: duplicate VARIABLES, placeholder text" in row["errors_rendered"]
    assert row["verify_summary"] == "tier=bronze sany=0 tlc=0 partial=0.000 struct=0.850"
    assert summary["rows"] == 1
    assert summary["failed_rows_seen"] == 1
    assert summary["gold_coverage"]["covered_failed_rows"] == 1
    assert summary["gold_coverage"]["missing_gold_benchmark_ids"] == []


def test_build_pairs_reports_missing_gold_coverage(tmp_path: Path) -> None:
    bench_suite = tmp_path / "data/benchmarks/benchmark_suite.json"
    _write(
        bench_suite,
        json.dumps([{"id": "BM003", "name": "Commit", "description": "Write commit spec."}]),
    )
    failed_csv = tmp_path / "outputs/benchmark_results/benchmark_results_fc128best_full.csv"
    _write_csv(
        failed_csv,
        [
            {
                "model": "chattla:20b-fc128best",
                "benchmark_id": "BM003",
                "name": "Commit",
                "domain": "txn",
                "difficulty": 3,
                "sany_pass": 0,
                "tlc_pass": 0,
                "structural_score": 0.7,
                "tlc_tier": "bronze",
                "runtime_s": 33.0,
                "generated_spec": "---- MODULE Commit ----\nCONSTDEF Foo == 1\n====",
                "init_present": 0,
                "next_present": 0,
                "init_level_ok": 0,
                "next_level_ok": 0,
                "invariants_declared": 0,
                "tlc_depth1_ok": 0,
                "partial_credit": 0.0,
                "expected_invariant_overlap": 0,
                "plan_used": 0,
            }
        ],
    )

    rows, summary = build_pairs(
        benchmark_suite_path=bench_suite,
        benchmark_to_module_path=tmp_path / "data/benchmarks/missing_benchmark_to_module.json",
        failed_csv_path=failed_csv,
        benchmark_dirs=(failed_csv.parent,),
        public_candidates_path=tmp_path / "data/processed/missing_public_candidates.jsonl",
        benchmark_model="chattla:20b-fc128best",
    )

    assert rows == []
    assert summary["rows"] == 0
    assert summary["failed_rows_seen"] == 1
    assert summary["gold_coverage"]["covered_failed_rows"] == 0
    assert summary["gold_coverage"]["missing_gold_benchmark_ids"] == ["BM003"]


def test_build_pairs_can_fallback_to_public_module_candidate(tmp_path: Path) -> None:
    bench_suite = tmp_path / "data/benchmarks/benchmark_suite.json"
    benchmark_to_module = tmp_path / "data/benchmarks/benchmark_to_module.json"
    public_candidates = tmp_path / "data/processed/ai4fm_public_seed_prover_candidates_v1.jsonl"
    _write(
        bench_suite,
        json.dumps(
            [
                {
                    "id": "BM020",
                    "name": "Eventually Consistent Counter",
                    "description": "Write a CRDT counter spec.",
                    "hints": "Use a grow-only counter.",
                }
            ]
        ),
    )
    _write(
        benchmark_to_module,
        json.dumps(
            {
                "mappings": [
                    {
                        "benchmark_id": "BM020",
                        "module_name": "CRDT",
                    }
                ]
            }
        ),
    )
    _write(
        public_candidates,
        json.dumps(
            {
                "module": "CRDT",
                "repo": "tlaplus/Examples",
                "source_path": "specifications/FiniteMonotonic/CRDT.tla",
                "content": "---- MODULE CRDT ----\nVARIABLE counter\nInit == counter = 0\nNext == counter' = counter\nSpec == Init /\\\\ [][Next]_counter\n====\n",
            }
        )
        + "\n",
    )
    failed_csv = tmp_path / "outputs/benchmark_results/benchmark_results_fc128best_full.csv"
    _write_csv(
        failed_csv,
        [
            {
                "model": "chattla:20b-fc128best",
                "benchmark_id": "BM020",
                "name": "Eventually Consistent Counter",
                "domain": "storage",
                "difficulty": 3,
                "sany_pass": 0,
                "tlc_pass": 0,
                "structural_score": 0.7,
                "tlc_tier": "bronze",
                "runtime_s": 24.0,
                "generated_spec": "---- MODULE GCounter ----\nCONSTDEF Foo == 1\n====",
                "init_present": 0,
                "next_present": 0,
                "init_level_ok": 0,
                "next_level_ok": 0,
                "invariants_declared": 0,
                "tlc_depth1_ok": 0,
                "partial_credit": 0.0,
                "expected_invariant_overlap": 0,
                "plan_used": 0,
            }
        ],
    )

    rows, summary = build_pairs(
        benchmark_suite_path=bench_suite,
        benchmark_to_module_path=benchmark_to_module,
        failed_csv_path=failed_csv,
        benchmark_dirs=(failed_csv.parent,),
        public_candidates_path=public_candidates,
        benchmark_model="chattla:20b-fc128best",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["benchmark_id"] == "BM020"
    assert row["repaired_spec"].startswith("---- MODULE CRDT ----")
    assert row["gold_source_csv"] == "ai4fm_public_seed_prover_candidates_v1.jsonl"
    assert row["gold_source_kind"] == "public_seed_prover_candidate"
    assert row["gold_source_module"] == "CRDT"
    assert row["gold_source_repo"] == "tlaplus/Examples"
    assert row["gold_source_path"] == "specifications/FiniteMonotonic/CRDT.tla"
    assert summary["rows"] == 1
    assert summary["gold_coverage"]["covered_failed_rows"] == 1
    assert summary["gold_coverage"]["missing_gold_benchmark_ids"] == []
    assert summary["public_module_fallback_benchmark_ids"] == ["BM020"]
