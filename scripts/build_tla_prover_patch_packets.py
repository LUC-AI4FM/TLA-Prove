#!/usr/bin/env python3
"""Build concrete patch packets for current pair-ready TLA prover repair targets."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.build_tla_prover_patch_worklist import IMMEDIATE_BUCKETS, _target_sort_key

DEFAULT_PATCH_WORKLIST = REPO / "outputs" / "manifests" / "tla_prover_patch_worklist.json"
DEFAULT_REPAIR_QUEUE = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_repair_queue.jsonl"
DEFAULT_REPAIR_EVIDENCE = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_repair_evidence.jsonl"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_patch_packets.json"


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


def _row_key(module_path: Any, module: Any) -> tuple[str, str]:
    return (str(module_path or "").strip(), str(module or "").strip())


def _build_packet(
    *,
    target: dict[str, Any],
    queue_row: dict[str, Any] | None,
    evidence_row: dict[str, Any] | None,
    repo: Path,
) -> dict[str, Any]:
    queue_row = queue_row or {}
    evidence_row = evidence_row or {}
    tlapm = dict(queue_row.get("tlapm") or {})
    module_path = Path(str(target.get("module_path") or queue_row.get("module_path") or evidence_row.get("module_path") or ""))
    broken_spec_path = Path(str(evidence_row.get("broken_spec_path") or module_path))
    packet = {
        "module": str(target.get("module") or queue_row.get("module") or evidence_row.get("module") or ""),
        "module_path": _display_path(module_path, repo) if str(module_path) else None,
        "repair_bucket": str(target.get("repair_bucket") or evidence_row.get("repair_bucket") or queue_row.get("repair_bucket") or ""),
        "repair_priority": str(target.get("repair_priority") or evidence_row.get("repair_priority") or queue_row.get("repair_priority") or ""),
        "recommended_action": str(target.get("recommended_action") or queue_row.get("recommended_action") or evidence_row.get("recommended_action") or ""),
        "status": str(target.get("status") or queue_row.get("status") or ""),
        "evidence_status": str(target.get("evidence_status") or evidence_row.get("evidence_status") or ""),
        "failure_excerpt": target.get("failure_excerpt") or queue_row.get("failure_excerpt") or evidence_row.get("failure_excerpt"),
        "target": queue_row.get("target") or evidence_row.get("target"),
        "runtime_seconds": queue_row.get("runtime_seconds") or evidence_row.get("runtime_seconds"),
        "obligations_failed": tlapm.get("obligations_failed"),
        "obligations_total": tlapm.get("obligations_total"),
        "before_score": target.get("before_score") if target.get("before_score") is not None else evidence_row.get("before_score"),
        "prompt_source_kind": target.get("prompt_source_kind") or evidence_row.get("prompt_source_kind"),
        "prompt_source_path": evidence_row.get("prompt_source_path"),
        "prompt_source_prompt_id": evidence_row.get("prompt_source_prompt_id"),
        "gold_source_kind": target.get("gold_source_kind") or evidence_row.get("gold_source_kind"),
        "gold_source_path": evidence_row.get("gold_source_path"),
        "gold_source_repo": evidence_row.get("gold_source_repo"),
        "broken_spec_path": _display_path(broken_spec_path, repo) if str(broken_spec_path) else None,
        "broken_spec_sha256": evidence_row.get("broken_spec_sha256"),
        "repaired_spec_sha256": evidence_row.get("repaired_spec_sha256"),
        "repaired_spec_chars": evidence_row.get("repaired_spec_chars"),
        "errors_rendered": evidence_row.get("errors_rendered"),
        "nl": evidence_row.get("nl"),
    }
    return packet


def build_packets(
    *,
    patch_worklist: Path = DEFAULT_PATCH_WORKLIST,
    repair_queue: Path = DEFAULT_REPAIR_QUEUE,
    repair_evidence: Path = DEFAULT_REPAIR_EVIDENCE,
    repo: Path = REPO,
) -> dict[str, Any]:
    worklist = _load_json(patch_worklist)
    queue_rows = _load_jsonl(repair_queue)
    evidence_rows = _load_jsonl(repair_evidence)

    queue_by_key = {_row_key(row.get("module_path"), row.get("module")): row for row in queue_rows}
    evidence_by_bucket: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in IMMEDIATE_BUCKETS}
    for row in evidence_rows:
        bucket = str(row.get("repair_bucket") or "")
        if bucket not in evidence_by_bucket or not bool(row.get("pair_ready")):
            continue
        evidence_by_bucket[bucket].append(row)

    packets_by_bucket: dict[str, list[dict[str, Any]]] = {}
    counts_by_bucket: dict[str, int] = {}
    for bucket in IMMEDIATE_BUCKETS:
        evidence_bucket_rows = list(evidence_by_bucket.get(bucket) or [])
        if not evidence_bucket_rows:
            continue
        bucket_packets: list[dict[str, Any]] = []
        for evidence_row in evidence_bucket_rows:
            key = _row_key(evidence_row.get("module_path"), evidence_row.get("module"))
            bucket_packets.append(
                _build_packet(
                    target=evidence_row,
                    queue_row=queue_by_key.get(key),
                    evidence_row=evidence_row,
                    repo=repo,
                )
            )
        if bucket_packets:
            bucket_packets.sort(key=lambda item, current=bucket: _target_sort_key(current, item))
            packets_by_bucket[str(bucket)] = bucket_packets
            counts_by_bucket[str(bucket)] = len(bucket_packets)

    primary_focus = dict(worklist.get("primary_focus") or {})
    primary_bucket = str(primary_focus.get("repair_bucket") or "")
    primary_focus_packets = list(packets_by_bucket.get(primary_bucket) or [])

    return {
        "schema": "chattla_tla_prover_patch_packets_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "patch_worklist": _display_path(patch_worklist, repo),
            "repair_queue": _display_path(repair_queue, repo),
            "repair_evidence": _display_path(repair_evidence, repo),
        },
        "primary_focus": primary_focus or None,
        "primary_focus_packets": primary_focus_packets,
        "counts_by_bucket": counts_by_bucket,
        "packets_by_bucket": packets_by_bucket,
        "recommended_next_step": worklist.get("recommended_next_step"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-worklist", type=Path, default=DEFAULT_PATCH_WORKLIST)
    parser.add_argument("--repair-queue", type=Path, default=DEFAULT_REPAIR_QUEUE)
    parser.add_argument("--repair-evidence", type=Path, default=DEFAULT_REPAIR_EVIDENCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    payload = build_packets(
        patch_worklist=args.patch_worklist,
        repair_queue=args.repair_queue,
        repair_evidence=args.repair_evidence,
        repo=REPO,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
