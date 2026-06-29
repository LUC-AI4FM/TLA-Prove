#!/usr/bin/env python3
"""Summarize a long-Ralph run from streamed step events.

This script is read-only: it inspects ``step_events.jsonl`` and clusters recent
failures by phase, family, and compact reason.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", nargs="?", default="")
    parser.add_argument("--recent", type=int, default=120)
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else latest_run_dir()
    if not run_dir.is_absolute():
        run_dir = _REPO_ROOT / run_dir

    steps = load_steps(run_dir / "step_events.jsonl")
    recent = steps[-args.recent:] if args.recent > 0 else steps

    report = {
        "run_dir": str(run_dir),
        "num_steps": len(steps),
        "recent_window": len(recent),
        "branch_steps": sum(1 for step in steps if step.get("branch_id") not in {"", None, "main"}),
        "phase_counts": dict(Counter(step.get("phase", "unknown") for step in recent)),
        "family_counts": dict(Counter(step.get("failure_family", "unknown") for step in recent)),
        "branch_counts": dict(Counter(step.get("branch_id", "main") for step in recent)),
        "reason_counts": dict(Counter(compact_reason(step) for step in recent).most_common(12)),
        "last_step": summarize_step(steps[-1]) if steps else {},
    }
    print(json.dumps(report, indent=2))
    return 0


def latest_run_dir() -> Path:
    runs = sorted(
        (_REPO_ROOT / "data/processed/long_ralph").glob("run_*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not runs:
        raise SystemExit("No long-Ralph run directories found.")
    return runs[0]


def load_steps(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"Missing step events: {path}")
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out.append(row.get("step", row))
    return out


def compact_reason(step: dict, limit: int = 180) -> str:
    reason = step.get("judge_reason") or step.get("diagnostics") or ""
    compacted = " ".join(str(reason).split())
    return compacted[:limit]


def summarize_step(step: dict) -> dict:
    semantic = step.get("semantic") or {}
    return {
        "iteration": step.get("iteration"),
        "phase": step.get("phase"),
        "tier": step.get("tier"),
        "score": step.get("score"),
        "success": step.get("success"),
        "failure_family": step.get("failure_family"),
        "branch_id": step.get("branch_id", "main"),
        "branch_focus": step.get("branch_focus", ""),
        "judge_ok": step.get("judge_ok"),
        "reason": compact_reason(step, limit=300),
        "properties_checked": semantic.get("properties_checked"),
        "properties_declared": semantic.get("properties_declared"),
        "property_names": semantic.get("property_names"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
