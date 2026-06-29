#!/usr/bin/env python3
"""Summarize GRPO completion-cap diagnostic runs.

Reads the PBS log produced by qsub_grpo_sophia_diag_caps*.pbs plus optional
sample JSONL files emitted by CHATTLA_SAMPLE_LOG_PATH, then prints a compact
cap-by-cap decision brief.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


_CAP_RE = re.compile(r"Starting (?:direct )?diagnostic cap=(\d+)")


def _to_float(row: dict[str, Any], key: str) -> float | None:
    try:
        return float(row[key])
    except Exception:
        return None


def _metric_rows(log_path: Path) -> dict[int, list[dict[str, Any]]]:
    by_cap: dict[int, list[dict[str, Any]]] = defaultdict(list)
    cap: int | None = None
    for raw_line in log_path.read_text(errors="replace").replace("\r", "\n").splitlines():
        m = _CAP_RE.search(raw_line)
        if m:
            cap = int(m.group(1))
            continue
        if cap is None or "learning_rate" not in raw_line:
            continue
        start = raw_line.find("{")
        end = raw_line.rfind("}")
        if start < 0 or end <= start:
            continue
        try:
            row = ast.literal_eval(raw_line[start:end + 1])
        except Exception:
            continue
        by_cap[cap].append(row)
    return dict(by_cap)


def _sample_rows(sample_paths: list[Path]) -> dict[int, list[dict[str, Any]]]:
    by_cap: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for path in sample_paths:
        cap_match = re.search(r"cap(\d+)", path.name)
        if not cap_match:
            continue
        cap = int(cap_match.group(1))
        with path.open(errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    by_cap[cap].append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return dict(by_cap)


def _summarize_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def vals(key: str) -> list[float]:
        out = []
        for row in rows:
            value = _to_float(row, key)
            if value is not None:
                out.append(value)
        return out

    clipped = vals("completions/clipped_ratio")
    reward = vals("reward")
    reward_std = vals("reward_std")
    terminated = vals("completions/mean_terminated_length")
    kl = vals("kl")
    return {
        "steps": len(rows),
        "clipped_mean": mean(clipped) if clipped else None,
        "clipped_lt_1": sum(v < 1.0 for v in clipped),
        "reward_mean": mean(reward) if reward else None,
        "reward_max": max(reward) if reward else None,
        "reward_nonzero": sum(v > 0 for v in reward),
        "reward_std_nonzero": sum(v > 0 for v in reward_std),
        "terminated_nonzero": sum(v > 0 for v in terminated),
        "kl_mean": mean(kl) if kl else None,
        "kl_max": max(kl) if kl else None,
    }


def _sample_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rewards = [float(row["reward"]) for row in rows if row.get("reward") is not None]
    extracted = [int(row.get("extracted_next_chars") or 0) for row in rows]
    raw = [int(row.get("raw_chars") or 0) for row in rows]
    empty_next = sum(v == 0 for v in extracted)
    raw_texts = [str(row.get("raw_completion") or "").lstrip() for row in rows]
    return {
        "samples": len(rows),
        "sample_reward_mean": mean(rewards) if rewards else None,
        "empty_extracted_next": empty_next,
        "analysis_start": sum(text.startswith("analysis") for text in raw_texts),
        "next_start": sum(text.startswith("Next ==") for text in raw_texts),
        "contains_next": sum("Next ==" in text for text in raw_texts),
        "raw_chars_mean": mean(raw) if raw else None,
        "extracted_next_chars_mean": mean(extracted) if extracted else None,
    }


def _recommend(cap_summaries: dict[int, dict[str, Any]]) -> str:
    candidates = []
    for cap, s in cap_summaries.items():
        clipped = s.get("clipped_mean")
        reward_std_nonzero = s.get("reward_std_nonzero", 0)
        steps = max(1, int(s.get("steps") or 0))
        reward_mean = s.get("reward_mean") or 0.0
        if clipped is not None and clipped < 0.8 and reward_std_nonzero >= steps / 2:
            candidates.append((reward_mean, -clipped, cap))
    if candidates:
        _, _, cap = max(candidates)
        return (
            f"Promote cap {cap}: clipped mean is below 0.8 and reward variance "
            "is present on at least half the logged steps."
        )
    if cap_summaries:
        best_cap = min(
            cap_summaries,
            key=lambda cap: (
                cap_summaries[cap].get("clipped_mean")
                if cap_summaries[cap].get("clipped_mean") is not None
                else 99.0
            ),
        )
        return (
            f"Do not promote yet. Best clipped ratio came from cap {best_cap}, "
            "but the promote gates were not met; inspect samples and tighten "
            "the prompt/output contract before another long phase."
        )
    return "No completed cap metrics found yet."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path, help="Main diagnostic PBS log")
    parser.add_argument(
        "--samples",
        nargs="*",
        type=Path,
        default=[],
        help="Sample JSONL files, usually outputs/logs/grpo_diag_cap*_samples.jsonl",
    )
    args = parser.parse_args()

    metrics = _metric_rows(args.log)
    samples = _sample_rows(args.samples)
    caps = sorted(set(metrics) | set(samples))

    combined: dict[int, dict[str, Any]] = {}
    for cap in caps:
        summary = _summarize_metrics(metrics.get(cap, []))
        summary.update(_sample_summary(samples.get(cap, [])))
        combined[cap] = summary

    print("# GRPO Diagnostic Cap Summary")
    print()
    for cap in caps:
        s = combined[cap]
        print(f"## cap {cap}")
        for key in (
            "steps",
            "clipped_mean",
            "clipped_lt_1",
            "reward_mean",
            "reward_max",
            "reward_nonzero",
            "reward_std_nonzero",
            "terminated_nonzero",
            "kl_mean",
            "kl_max",
            "samples",
            "sample_reward_mean",
            "empty_extracted_next",
            "analysis_start",
            "next_start",
            "contains_next",
            "raw_chars_mean",
            "extracted_next_chars_mean",
        ):
            value = s.get(key)
            if isinstance(value, float):
                value = round(value, 6)
            print(f"- {key}: {value}")
        print()

    print("## recommendation")
    print(_recommend(combined))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
