#!/usr/bin/env python3
"""Build a compact, pair-ready patch worklist from current TLA prover artifacts."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REPAIR_QUEUE = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_repair_queue.jsonl"
DEFAULT_REPAIR_EVIDENCE = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_repair_evidence.jsonl"
DEFAULT_FAILURE_ANALYSIS = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_failure_analysis.json"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_patch_worklist.json"
IMMEDIATE_BUCKETS = ("proof_repair", "inductiveness_repair", "tlc_repair", "skip_harness_repair")
BLOCKED_BUCKETS = ("skip_missing_contract", "skip_sany_invalid", "skip_other")


def _display_path(path: Path, repo: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("module_path") or "").strip(),
        str(row.get("module") or "").strip(),
    )


def _bucket_order(bucket: str) -> int:
    try:
        return IMMEDIATE_BUCKETS.index(bucket)
    except ValueError:
        return len(IMMEDIATE_BUCKETS)


def _proof_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    return (
        -int(row.get("obligations_failed") or 0),
        -int(row.get("obligations_total") or 0),
        str(row.get("module") or "").lower(),
    )


def _inductive_sort_key(row: dict[str, Any]) -> tuple[float, str]:
    score = row.get("before_score")
    return (
        float(score) if score is not None else 1.0,
        str(row.get("module") or "").lower(),
    )


def _tlc_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("tlc_error_family") or ""),
        str(row.get("module") or "").lower(),
    )


def _harness_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("skip_reason_family") or ""),
        str(row.get("module") or "").lower(),
    )


def _target_sort_key(bucket: str, row: dict[str, Any]) -> tuple[Any, ...]:
    if bucket == "proof_repair":
        return _proof_sort_key(row)
    if bucket == "inductiveness_repair":
        return _inductive_sort_key(row)
    if bucket == "tlc_repair":
        return _tlc_sort_key(row)
    if bucket == "skip_harness_repair":
        return _harness_sort_key(row)
    return (str(row.get("module") or "").lower(),)


def _unique_modules(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    modules: list[str] = []
    for row in rows:
        module = str(row.get("module") or "").strip()
        if not module or module in seen:
            continue
        seen.add(module)
        modules.append(module)
    return modules


def _merge_target(
    *,
    queue_row: dict[str, Any] | None,
    evidence_row: dict[str, Any],
    repo: Path,
) -> dict[str, Any]:
    queue_row = queue_row or {}
    tlapm = dict(queue_row.get("tlapm") or {})
    module_path = Path(str(queue_row.get("module_path") or evidence_row.get("module_path") or ""))
    return {
        "module": str(evidence_row.get("module") or queue_row.get("module") or ""),
        "module_path": _display_path(module_path, repo) if str(module_path) else None,
        "repair_bucket": str(evidence_row.get("repair_bucket") or queue_row.get("repair_bucket") or ""),
        "repair_priority": str(evidence_row.get("repair_priority") or queue_row.get("repair_priority") or ""),
        "recommended_action": str(queue_row.get("recommended_action") or ""),
        "status": str(queue_row.get("status") or ""),
        "evidence_status": str(evidence_row.get("evidence_status") or ""),
        "before_score": evidence_row.get("before_score"),
        "prompt_source_kind": evidence_row.get("prompt_source_kind"),
        "gold_source_kind": evidence_row.get("gold_source_kind"),
        "failure_excerpt": queue_row.get("failure_excerpt"),
        "tlc_error_family": queue_row.get("tlc_error_family"),
        "skip_reason_family": queue_row.get("skip_reason_family"),
        "obligations_failed": tlapm.get("obligations_failed"),
        "obligations_total": tlapm.get("obligations_total"),
    }


def build_worklist(
    *,
    repair_queue: Path = DEFAULT_REPAIR_QUEUE,
    repair_evidence: Path = DEFAULT_REPAIR_EVIDENCE,
    failure_analysis: Path = DEFAULT_FAILURE_ANALYSIS,
    repo: Path = REPO,
    top_n: int = 5,
) -> dict[str, Any]:
    queue_rows = _load_jsonl(repair_queue)
    evidence_rows = _load_jsonl(repair_evidence)
    failure = _load_json(failure_analysis)

    queue_by_key = {_row_key(row): row for row in queue_rows}
    bucket_summary: dict[str, dict[str, Any]] = {
        bucket: {"queue_rows": 0, "pair_ready_rows": 0, "evidence_status_counts": {}}
        for bucket in IMMEDIATE_BUCKETS
    }
    for row in queue_rows:
        bucket = str(row.get("repair_bucket") or "")
        if bucket in bucket_summary:
            bucket_summary[bucket]["queue_rows"] += 1

    targets_by_bucket: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in IMMEDIATE_BUCKETS}
    evidence_status_counts_by_bucket: dict[str, Counter[str]] = {bucket: Counter() for bucket in IMMEDIATE_BUCKETS}
    pair_ready_counts: Counter[str] = Counter()
    for row in evidence_rows:
        bucket = str(row.get("repair_bucket") or "")
        if bucket not in bucket_summary:
            continue
        status = str(row.get("evidence_status") or "")
        if status:
            evidence_status_counts_by_bucket[bucket][status] += 1
        if bool(row.get("pair_ready")):
            pair_ready_counts[bucket] += 1
            targets_by_bucket[bucket].append(
                _merge_target(queue_row=queue_by_key.get(_row_key(row)), evidence_row=row, repo=repo)
            )

    for bucket in IMMEDIATE_BUCKETS:
        bucket_summary[bucket]["pair_ready_rows"] = pair_ready_counts.get(bucket, 0)
        bucket_summary[bucket]["evidence_status_counts"] = dict(sorted(evidence_status_counts_by_bucket[bucket].items()))
        targets_by_bucket[bucket].sort(key=lambda item, current=bucket: _target_sort_key(current, item))
        targets_by_bucket[bucket] = targets_by_bucket[bucket][:top_n]

    focus_candidates = [
        {
            "repair_bucket": bucket,
            "queue_rows": bucket_summary[bucket]["queue_rows"],
            "pair_ready_rows": bucket_summary[bucket]["pair_ready_rows"],
            "top_modules": _unique_modules(targets_by_bucket[bucket]),
        }
        for bucket in IMMEDIATE_BUCKETS
        if bucket_summary[bucket]["pair_ready_rows"] > 0
    ]
    focus_candidates.sort(
        key=lambda item: (
            _bucket_order(str(item["repair_bucket"])),
            -int(item["pair_ready_rows"]),
            -int(item["queue_rows"]),
        )
    )
    primary_focus = None
    secondary_focuses: list[dict[str, Any]] = []
    if focus_candidates:
        primary_focus = dict(focus_candidates[0])
        primary_focus["reason"] = (
            "Highest-priority immediate repair bucket with pair-ready targets available now."
        )
        secondary_focuses = focus_candidates[1:]

    blocked_row_counts = {
        bucket: int(dict(failure.get("action_bucket_counts") or {}).get(bucket) or 0)
        for bucket in BLOCKED_BUCKETS
    }
    recommended_next_step = (
        "No pair-ready patch targets are currently available; regenerate repair evidence or expand public gold coverage."
    )
    if primary_focus is not None:
        recommended_next_step = (
            f"Start with {primary_focus['repair_bucket']} because it is the highest-priority immediate bucket "
            f"with {primary_focus['pair_ready_rows']} pair-ready rows ready for patch work now."
        )

    return {
        "schema": "chattla_tla_prover_patch_worklist_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "repair_queue": _display_path(repair_queue, repo),
            "repair_evidence": _display_path(repair_evidence, repo),
            "failure_analysis": _display_path(failure_analysis, repo),
        },
        "immediate_repair_rows": failure.get("immediate_repair_rows"),
        "blocked_row_counts": blocked_row_counts,
        "bucket_summary": bucket_summary,
        "primary_focus": primary_focus,
        "secondary_focuses": secondary_focuses,
        "top_targets_by_bucket": targets_by_bucket,
        "recommended_next_step": recommended_next_step,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-queue", type=Path, default=DEFAULT_REPAIR_QUEUE)
    parser.add_argument("--repair-evidence", type=Path, default=DEFAULT_REPAIR_EVIDENCE)
    parser.add_argument("--failure-analysis", type=Path, default=DEFAULT_FAILURE_ANALYSIS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--top-n", type=int, default=5)
    args = parser.parse_args()

    payload = build_worklist(
        repair_queue=args.repair_queue,
        repair_evidence=args.repair_evidence,
        failure_analysis=args.failure_analysis,
        repo=REPO,
        top_n=args.top_n,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
