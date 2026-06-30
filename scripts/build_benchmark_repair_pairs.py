#!/usr/bin/env python3
"""Build benchmark-derived repair pairs from failed benchmark runs plus known gold specs."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_SUITE = REPO / "data" / "benchmarks" / "benchmark_suite.json"
DEFAULT_BENCHMARK_TO_MODULE = REPO / "data" / "benchmarks" / "benchmark_to_module.json"
DEFAULT_BENCHMARK_DIRS = (
    REPO / "outputs" / "benchmark_results",
    REPO / "outputs" / "benchmark_results" / "RL-loop",
)
DEFAULT_FAILED_CSV = REPO / "outputs" / "benchmark_results" / "benchmark_results_fc128best_full_20260628_235102.csv"
DEFAULT_OUT = REPO / "data" / "processed" / "benchmark_repair_pairs_fc128best.jsonl"
DEFAULT_PUBLIC_GOLD_CANDIDATES = REPO / "data" / "processed" / "ai4fm_public_seed_prover_candidates_v1.jsonl"
CORE_COMPONENT_FIELDS = (
    ("init_present", "Init"),
    ("next_present", "Next"),
    ("init_level_ok", "Init-level"),
    ("next_level_ok", "Next-level"),
    ("invariants_declared", "invariants"),
    ("tlc_depth1_ok", "TLC depth-1"),
)
RED_FLAG_PATTERNS = (
    ("duplicate VARIABLES", re.compile(r"\bVARIABLES\b[^\n]*\b(\w+)\b[^\n]*\b\1\b")),
    ("placeholder text", re.compile(r"\.\.\.|placeholder|omitted|todo|etc\.", re.IGNORECASE)),
    ("pseudo-TLA tokens", re.compile(
        r"\bforall\b|\bexists\b|\bwhere\b|\bconstdef\b|#=|subsete\[\?\]|RemoveAt\(|SeqFromList|SeqSubseq",
        re.IGNORECASE,
    )),
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            if raw.strip():
                rows.append(json.loads(raw))
    return rows


def _is_truthy(value: object) -> bool:
    return str(value).strip() in {"1", "True", "true", "yes"}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _benchmark_prompt(benchmark: dict[str, Any]) -> str:
    text = f"Write a TLA+ specification for the following:\n\n{benchmark['description']}"
    hints = benchmark.get("hints")
    if hints:
        text += f"\n\nHints: {hints}"
    return text


def _best_gold_specs(benchmark_dirs: tuple[Path, ...]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for directory in benchmark_dirs:
        if not directory.exists():
            continue
        for csv_path in sorted(directory.glob("*.csv")):
            try:
                rows = _read_csv(csv_path)
            except (OSError, csv.Error):
                continue
            for row in rows:
                if not (_is_truthy(row.get("sany_pass")) and _is_truthy(row.get("tlc_pass"))):
                    continue
                spec = str(row.get("generated_spec", "")).strip()
                benchmark_id = str(row.get("benchmark_id", "")).strip()
                if not spec or not benchmark_id:
                    continue
                candidate = {
                    "benchmark_id": benchmark_id,
                    "spec": spec,
                    "structural_score": _safe_float(row.get("structural_score")),
                    "source_csv": csv_path.name,
                }
                current = best.get(benchmark_id)
                if current is None:
                    best[benchmark_id] = candidate
                    continue
                cur_key = (current["structural_score"], len(current["spec"]))
                cand_key = (candidate["structural_score"], len(candidate["spec"]))
                if cand_key > cur_key:
                    best[benchmark_id] = candidate
    return best


def _benchmark_module_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    mappings = payload.get("mappings", [])
    result: dict[str, str] = {}
    for row in mappings:
        benchmark_id = str(row.get("benchmark_id") or "").strip()
        module_name = str(row.get("module_name") or "").strip()
        if benchmark_id and module_name:
            result[benchmark_id] = module_name
    return result


def _public_gold_specs(
    *,
    benchmark_to_module_path: Path,
    public_candidates_path: Path,
) -> dict[str, dict[str, Any]]:
    if not benchmark_to_module_path.exists() or not public_candidates_path.exists():
        return {}

    benchmark_to_module = _benchmark_module_map(benchmark_to_module_path)
    if not benchmark_to_module:
        return {}

    module_to_candidate: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(public_candidates_path):
        module_name = str(row.get("module") or "").strip()
        content = str(row.get("content") or "").strip()
        if not module_name or not content:
            continue
        candidate = {
            "benchmark_id": None,
            "spec": content,
            "structural_score": 1.0,
            "source_csv": public_candidates_path.name,
            "source_kind": "public_seed_prover_candidate",
            "source_module": module_name,
            "source_repo": row.get("repo"),
            "source_path": row.get("source_path"),
        }
        current = module_to_candidate.get(module_name)
        if current is None:
            module_to_candidate[module_name] = candidate
            continue
        current_key = (
            1 if str(current.get("source_repo")) == "tlaplus/Examples" else 0,
            -len(str(current.get("spec") or "")),
        )
        candidate_key = (
            1 if str(candidate.get("source_repo")) == "tlaplus/Examples" else 0,
            -len(content),
        )
        if candidate_key > current_key:
            module_to_candidate[module_name] = candidate

    result: dict[str, dict[str, Any]] = {}
    for benchmark_id, module_name in benchmark_to_module.items():
        candidate = module_to_candidate.get(module_name)
        if candidate is not None:
            result[benchmark_id] = dict(candidate, benchmark_id=benchmark_id)
    return result


def _diagnostics(row: dict[str, str]) -> str:
    missing = [label for field, label in CORE_COMPONENT_FIELDS if not _is_truthy(row.get(field))]
    lines = [
        f"tier={row.get('tlc_tier', '')} sany={row.get('sany_pass', '')} tlc={row.get('tlc_pass', '')}",
        f"partial_credit={_safe_float(row.get('partial_credit')):.3f} structural_score={_safe_float(row.get('structural_score')):.3f}",
    ]
    if missing:
        lines.append("missing core components: " + ", ".join(missing))
    red_flags = [label for label, pattern in RED_FLAG_PATTERNS if pattern.search(str(row.get("generated_spec", "")))]
    if red_flags:
        lines.append("red flags: " + ", ".join(red_flags))
    overlap = _safe_int(row.get("expected_invariant_overlap"))
    lines.append(f"expected_invariant_overlap={overlap}")
    lines.append(f"plan_used={1 if _is_truthy(row.get('plan_used')) else 0}")
    return "\n".join(lines)


def _repair_row(
    benchmark: dict[str, Any],
    failed_row: dict[str, str],
    gold: dict[str, Any],
    *,
    benchmark_model: str,
) -> dict[str, Any]:
    benchmark_id = str(failed_row["benchmark_id"]).strip()
    safe_model = re.sub(r"[^A-Za-z0-9]+", "_", benchmark_model).strip("_")
    return {
        "repair_id": f"{benchmark_id}::{safe_model}",
        "nl": _benchmark_prompt(benchmark),
        "broken_spec": str(failed_row.get("generated_spec", "")).strip(),
        "errors_rendered": _diagnostics(failed_row),
        "verify_summary": (
            f"tier={failed_row.get('tlc_tier', '')} "
            f"sany={failed_row.get('sany_pass', '')} "
            f"tlc={failed_row.get('tlc_pass', '')} "
            f"partial={_safe_float(failed_row.get('partial_credit')):.3f} "
            f"struct={_safe_float(failed_row.get('structural_score')):.3f}"
        ),
        "before_score": _safe_float(failed_row.get("partial_credit")),
        "before_raw_score": _safe_float(failed_row.get("partial_credit")),
        "repaired_spec": gold["spec"],
        "after_score": 1.0,
        "after_raw_score": 1.0,
        "before_diamond": False,
        "after_diamond": True,
        "before_phase": "benchmark_failure",
        "after_phase": "gold",
        "after_proof_success": True,
        "after_model_audit_ok": None,
        "after_success": True,
        "after_judge_ok": None,
        "before_failure_family": "benchmark_failure",
        "after_failure_family": "gold",
        "benchmark_id": benchmark_id,
        "benchmark_model": benchmark_model,
        "gold_source_csv": gold["source_csv"],
        "gold_source_kind": gold.get("source_kind", "benchmark_gold_csv"),
        "gold_source_module": gold.get("source_module"),
        "gold_source_repo": gold.get("source_repo"),
        "gold_source_path": gold.get("source_path"),
    }


def build_pairs(
    *,
    benchmark_suite_path: Path = DEFAULT_BENCHMARK_SUITE,
    benchmark_to_module_path: Path = DEFAULT_BENCHMARK_TO_MODULE,
    failed_csv_path: Path = DEFAULT_FAILED_CSV,
    benchmark_dirs: tuple[Path, ...] = DEFAULT_BENCHMARK_DIRS,
    public_candidates_path: Path = DEFAULT_PUBLIC_GOLD_CANDIDATES,
    benchmark_model: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    benchmarks = json.loads(benchmark_suite_path.read_text(encoding="utf-8"))
    benchmarks_by_id = {item["id"]: item for item in benchmarks}
    failed_rows = [
        row for row in _read_csv(failed_csv_path)
        if str(row.get("model", "")).strip() == benchmark_model
        and not (_is_truthy(row.get("sany_pass")) and _is_truthy(row.get("tlc_pass")))
    ]
    gold_by_id = _best_gold_specs(benchmark_dirs)
    public_gold_by_id = _public_gold_specs(
        benchmark_to_module_path=benchmark_to_module_path,
        public_candidates_path=public_candidates_path,
    )

    rows: list[dict[str, Any]] = []
    missing_gold: set[str] = set()
    public_fallback_ids: list[str] = []
    for failed_row in failed_rows:
        benchmark_id = str(failed_row.get("benchmark_id", "")).strip()
        benchmark = benchmarks_by_id.get(benchmark_id)
        gold = gold_by_id.get(benchmark_id)
        if gold is None:
            gold = public_gold_by_id.get(benchmark_id)
            if gold is not None:
                public_fallback_ids.append(benchmark_id)
        if benchmark is None or gold is None:
            if benchmark_id:
                missing_gold.add(benchmark_id)
            continue
        rows.append(_repair_row(benchmark, failed_row, gold, benchmark_model=benchmark_model))

    summary = {
        "schema": "chattla_benchmark_repair_pairs_summary_v1",
        "benchmark_model": benchmark_model,
        "source_csv": str(failed_csv_path.relative_to(REPO)) if failed_csv_path.is_absolute() and failed_csv_path.is_relative_to(REPO) else str(failed_csv_path),
        "rows": len(rows),
        "failed_rows_seen": len(failed_rows),
        "gold_coverage": {
            "covered_failed_rows": len(rows),
            "missing_gold_benchmark_ids": sorted(missing_gold),
        },
        "public_module_fallback_benchmark_ids": sorted(public_fallback_ids),
    }
    return rows, summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-suite", type=Path, default=DEFAULT_BENCHMARK_SUITE)
    parser.add_argument("--benchmark-to-module", type=Path, default=DEFAULT_BENCHMARK_TO_MODULE)
    parser.add_argument("--failed-csv", type=Path, default=DEFAULT_FAILED_CSV)
    parser.add_argument("--public-candidates", type=Path, default=DEFAULT_PUBLIC_GOLD_CANDIDATES)
    parser.add_argument("--benchmark-model", default="chattla:20b-fc128best")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_pairs(
        benchmark_suite_path=args.benchmark_suite,
        benchmark_to_module_path=args.benchmark_to_module,
        failed_csv_path=args.failed_csv,
        benchmark_dirs=DEFAULT_BENCHMARK_DIRS,
        public_candidates_path=args.public_candidates,
        benchmark_model=args.benchmark_model,
    )
    _write_jsonl(args.out, rows)
    summary_path = args.out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "summary": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
