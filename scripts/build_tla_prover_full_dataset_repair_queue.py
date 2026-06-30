#!/usr/bin/env python3
"""Materialize a prioritized repair queue from a full-dataset autoprover smoke run."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.build_tla_prover_full_dataset_failure_analysis import _action_bucket
from scripts.summarize_autoprover_smoke import _load_rows, _skip_reason_family, _tlc_error_family

DEFAULT_JSONL = REPO / "outputs" / "autoprover" / "full_dataset_smoke_161031.jsonl"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_repair_queue.jsonl"

PRIORITY_BY_BUCKET = {
    "proof_replay_ready": ("p1", "rerun_with_tlaps"),
    "proof_repair": ("p1", "collect_proof_repair_pair"),
    "inductiveness_repair": ("p2", "collect_inductiveness_repair_pair"),
    "tlc_repair": ("p3", "collect_tlc_repair_pair"),
    "skip_harness_repair": ("p4", "patch_harness_and_replay"),
}

PRIORITY_ORDER = ("p1", "p2", "p3", "p4")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _proof_excerpt(row: dict[str, Any]) -> str:
    tlapm = dict(row.get("tlapm") or {})
    for error in tlapm.get("errors") or []:
        text = str(error).strip()
        if text:
            return text
    raw_tail = str(tlapm.get("raw_tail") or "")
    for line in raw_tail.splitlines():
        text = line.strip()
        if text:
            return text[:280]
    return "TLAPS obligations failed."


def _inductiveness_excerpt(row: dict[str, Any]) -> str:
    preview = str(row.get("cti_preview") or "").strip()
    if not preview:
        return "Invariant counterexample requires repair."
    return preview.splitlines()[0][:280]


def _tlc_excerpt(row: dict[str, Any]) -> str:
    error = str(row.get("tlc_error") or "").strip()
    if not error:
        return "TLC produced no conclusive result."
    return error.splitlines()[0][:280]


def _queue_tlc_error_family(error: str) -> str:
    if "Attempted to apply function" in error or "Attempted to apply the tuple" in error:
        return "function_or_operator_shape"
    return _tlc_error_family(error)


def _sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    priority = str(item.get("repair_priority", ""))
    priority_rank = PRIORITY_ORDER.index(priority) if priority in PRIORITY_ORDER else len(PRIORITY_ORDER)
    proof_failed = int(dict(item.get("tlapm") or {}).get("obligations_failed") or 0)
    return (
        priority_rank,
        -proof_failed,
        str(item.get("module_path") or "").lower(),
        str(item.get("module") or "").lower(),
    )


def build_queue(*, jsonl_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows = _load_rows(jsonl_path)
    rows: list[dict[str, Any]] = []
    repair_bucket_counts = Counter()
    priority_counts = Counter()
    recommended_action_counts = Counter()
    excluded_bucket_counts = Counter()
    tlc_error_family_counts = Counter()

    for row in raw_rows:
        bucket = _action_bucket(row)
        priority_info = PRIORITY_BY_BUCKET.get(bucket)
        if priority_info is None:
            excluded_bucket_counts[bucket] += 1
            continue
        repair_priority, recommended_action = priority_info
        item: dict[str, Any] = {
            "module": row.get("module"),
            "module_path": row.get("module_path"),
            "target": row.get("target"),
            "status": row.get("status"),
            "repair_bucket": bucket,
            "repair_priority": repair_priority,
            "recommended_action": recommended_action,
            "runtime_seconds": row.get("runtime_seconds"),
        }
        if bucket == "proof_repair":
            tlapm = dict(row.get("tlapm") or {})
            item["tlapm"] = {
                "tier": tlapm.get("tier"),
                "obligations_total": int(tlapm.get("obligations_total") or 0),
                "obligations_proved": int(tlapm.get("obligations_proved") or 0),
                "obligations_failed": int(tlapm.get("obligations_failed") or 0),
            }
            item["failure_excerpt"] = _proof_excerpt(row)
        elif bucket == "proof_replay_ready":
            item["failure_excerpt"] = (
                "Inductiveness and harness checks now pass locally; rerun this module with TLAPS enabled to collect proof outcomes."
            )
        elif bucket == "inductiveness_repair":
            item["failure_excerpt"] = _inductiveness_excerpt(row)
            if row.get("cti_preview"):
                item["cti_preview"] = str(row.get("cti_preview"))[:600]
        elif bucket == "tlc_repair":
            tlc_error = str(row.get("tlc_error") or "")
            tlc_error_family = _queue_tlc_error_family(tlc_error)
            item["tlc_error_family"] = tlc_error_family
            item["failure_excerpt"] = _tlc_excerpt(row)
            tlc_error_family_counts[tlc_error_family] += 1
        else:
            reason = str(row.get("reason") or "")
            item["reason"] = reason
            item["skip_reason_family"] = _skip_reason_family(reason)
            item["failure_excerpt"] = reason or "Harness/domain gap requires replay."
        rows.append(item)
        repair_bucket_counts[bucket] += 1
        priority_counts[repair_priority] += 1
        recommended_action_counts[recommended_action] += 1

    rows.sort(key=_sort_key)
    top_modules_by_bucket: dict[str, list[str]] = {}
    for bucket in PRIORITY_BY_BUCKET:
        modules = [str(row.get("module")) for row in rows if row.get("repair_bucket") == bucket]
        if modules:
            top_modules_by_bucket[bucket] = modules[:12]

    summary = {
        "schema": "chattla_tla_prover_full_dataset_repair_queue_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_jsonl": _display_path(jsonl_path),
        "rows": len(rows),
        "repair_bucket_counts": {key: repair_bucket_counts.get(key, 0) for key in PRIORITY_BY_BUCKET},
        "priority_counts": {key: priority_counts.get(key, 0) for key in PRIORITY_ORDER if priority_counts.get(key, 0)},
        "recommended_action_counts": dict(sorted(recommended_action_counts.items())),
        "excluded_bucket_counts": dict(sorted((k, v) for k, v in excluded_bucket_counts.items() if v)),
        "tlc_error_family_counts": dict(sorted(tlc_error_family_counts.items())),
        "top_modules_by_bucket": top_modules_by_bucket,
        "stage_plan": [
            {
                "priority": "p1",
                "bucket": "proof_replay_ready",
                "recommended_action": "rerun_with_tlaps",
                "rows": repair_bucket_counts.get("proof_replay_ready", 0),
                "note": "Local harness/inductiveness replay succeeded; run in a TLAPS-enabled environment to surface proof outcomes.",
            },
            {
                "priority": "p1",
                "bucket": "proof_repair",
                "recommended_action": "collect_proof_repair_pair",
                "rows": repair_bucket_counts.get("proof_repair", 0),
                "note": "Highest-value TLAPS partials for direct proof repair supervision.",
            },
            {
                "priority": "p2",
                "bucket": "inductiveness_repair",
                "recommended_action": "collect_inductiveness_repair_pair",
                "rows": repair_bucket_counts.get("inductiveness_repair", 0),
                "note": "Counterexample-guided invariant repair targets.",
            },
            {
                "priority": "p3",
                "bucket": "tlc_repair",
                "recommended_action": "collect_tlc_repair_pair",
                "rows": repair_bucket_counts.get("tlc_repair", 0),
                "note": "TLC/runtime repair targets with concrete evaluator failures.",
            },
            {
                "priority": "p4",
                "bucket": "skip_harness_repair",
                "recommended_action": "patch_harness_and_replay",
                "rows": repair_bucket_counts.get("skip_harness_repair", 0),
                "note": "Rows blocked by bounded-domain or harness-shape gaps rather than proof content alone.",
            },
        ],
    }
    return rows, summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_queue(jsonl_path=args.jsonl)
    _write_jsonl(args.out, rows)
    summary_path = args.out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
