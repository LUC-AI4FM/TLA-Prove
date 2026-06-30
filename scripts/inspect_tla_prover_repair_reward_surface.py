#!/usr/bin/env python3
"""Summarize the oracle repair-reward signal already present in a repair corpus."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO / "data" / "processed" / "tla_prover_repair_train_proof_repair_primary_v1.jsonl"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.rlvr_canary.repair_reward import _shape_reward


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def build_reward_surface_summary(path: Path) -> dict[str, Any]:
    rows = _read_jsonl(path)
    rewards: list[float] = []
    deltas: list[float] = []
    by_bucket: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    missing_after_score = 0

    for row in rows:
        before = row.get("before_score")
        after = row.get("after_score")
        if before is None or after is None:
            missing_after_score += 1
            continue
        before_f = float(before)
        after_f = float(after)
        rewards.append(_shape_reward(before_f, after_f))
        deltas.append(after_f - before_f)
        bucket = str(row.get("repair_bucket") or "").strip()
        if bucket:
            by_bucket[bucket] += 1
        source = str(row.get("source_file") or "").strip()
        if source:
            by_source[source] += 1

    positive_reward_rows = sum(1 for reward in rewards if reward > 0.15)
    return {
        "schema": "chattla_tla_prover_repair_reward_surface_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_path": _display_path(path),
        "rows": len(rows),
        "rows_with_after_score": len(rewards),
        "rows_missing_after_score": missing_after_score,
        "oracle_reward": {
            "mean": statistics.mean(rewards) if rewards else None,
            "median": statistics.median(rewards) if rewards else None,
            "min": min(rewards) if rewards else None,
            "max": max(rewards) if rewards else None,
            "positive_reward_rows": positive_reward_rows,
            "positive_reward_ratio": (positive_reward_rows / len(rewards)) if rewards else None,
        },
        "oracle_delta": {
            "mean": statistics.mean(deltas) if deltas else None,
            "median": statistics.median(deltas) if deltas else None,
            "min": min(deltas) if deltas else None,
            "max": max(deltas) if deltas else None,
        },
        "rows_by_repair_bucket": dict(sorted(by_bucket.items())),
        "rows_by_source_file": dict(sorted(by_source.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    summary = build_reward_surface_summary(args.input)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
