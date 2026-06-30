#!/usr/bin/env python3
"""Compare two eval_fullspec_checkpoints.py JSON summaries."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SCHEMA = "chattla.tla_prover_eval_comparison.v1"
MAIN_IMPROVEMENT_METRICS = (
    "sany_pass",
    "depth1_pass",
    "tlc_pass",
    "mean_reward",
)
ALL_METRICS = MAIN_IMPROVEMENT_METRICS + (
    "module_match",
    "syntax_issue_rows",
    "syntax_issue_count",
)
FLOAT_METRICS = {"mean_reward"}
LOWER_IS_BETTER_METRICS = {"syntax_issue_rows", "syntax_issue_count"}


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path.resolve())


def _load_json_object(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise SystemExit(f"missing JSON file: {path}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"expected JSON object in {path}")
    return payload


def _metric_value(row: dict[str, Any], key: str) -> int | float:
    value = row.get(key, 0.0 if key in FLOAT_METRICS else 0)
    if value is None:
        value = 0.0 if key in FLOAT_METRICS else 0
    if key in FLOAT_METRICS:
        return round(float(value), 6)
    return int(value)


def _normalized_summary(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "label": str(row.get("label") or path.stem),
        "n": int(row.get("n", 0) or 0),
    }
    for metric in ALL_METRICS:
        summary[metric] = _metric_value(row, metric)
    return summary


def compare_eval_results(baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    baseline_raw = _load_json_object(Path(baseline_path))
    candidate_raw = _load_json_object(Path(candidate_path))
    baseline = _normalized_summary(Path(baseline_path), baseline_raw)
    candidate = _normalized_summary(Path(candidate_path), candidate_raw)

    deltas: dict[str, int | float] = {}
    for metric in ALL_METRICS:
        delta = candidate[metric] - baseline[metric]
        deltas[metric] = round(delta, 6) if metric in FLOAT_METRICS else delta

    checks = {
        "same_n": candidate["n"] == baseline["n"],
        "sany_no_regression": candidate["sany_pass"] >= baseline["sany_pass"],
        "depth1_no_regression": candidate["depth1_pass"] >= baseline["depth1_pass"],
        "tlc_no_regression": candidate["tlc_pass"] >= baseline["tlc_pass"],
        "reward_no_regression": candidate["mean_reward"] >= baseline["mean_reward"],
        "module_match_no_regression": candidate["module_match"] >= baseline["module_match"],
        "syntax_issue_rows_no_regression": candidate["syntax_issue_rows"] <= baseline["syntax_issue_rows"],
        "syntax_issue_count_no_regression": candidate["syntax_issue_count"] <= baseline["syntax_issue_count"],
    }
    improves_any = any(candidate[metric] > baseline[metric] for metric in MAIN_IMPROVEMENT_METRICS)
    eligible = bool(checks["same_n"] and all(checks[name] for name in checks if name != "same_n") and improves_any)
    failed_checks = [name for name, ok in checks.items() if not ok]

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "baseline_path": _display_path(Path(baseline_path)),
        "candidate_path": _display_path(Path(candidate_path)),
        "baseline": baseline,
        "candidate": candidate,
        "deltas": deltas,
        "checks": checks,
        "improves_any": improves_any,
        "eligible": eligible,
        "failed_checks": failed_checks,
    }


def _format_delta(name: str, value: int | float) -> str:
    if name in FLOAT_METRICS:
        return f"{name} {value:+.6f}"
    return f"{name} {value:+d}"


def _print_summary(report: dict[str, Any]) -> None:
    deltas = report["deltas"]
    print(
        "[compare-eval]",
        f"baseline={report['baseline']['label']}",
        f"candidate={report['candidate']['label']}",
        f"n={report['candidate']['n']}",
        _format_delta("sany", deltas["sany_pass"]),
        _format_delta("depth1", deltas["depth1_pass"]),
        _format_delta("tlc", deltas["tlc_pass"]),
        _format_delta("mean_reward", deltas["mean_reward"]),
        f"eligible={report['eligible']}",
    )
    if report["failed_checks"]:
        print("[compare-eval] failed_checks", ",".join(report["failed_checks"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = compare_eval_results(Path(args.baseline), Path(args.candidate))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_summary(report)
    print(f"[compare-eval] wrote {_display_path(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
