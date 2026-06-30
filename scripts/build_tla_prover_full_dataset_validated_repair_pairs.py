#!/usr/bin/env python3
"""Promote pair-ready full-dataset repair evidence into validator-backed repair pairs."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
DEFAULT_EVIDENCE = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_repair_evidence.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "tla_prover_full_dataset_validated_repair_pairs_v1.jsonl"

from src.validators.tlc_validator import validate_string


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _display_path(path: Path, repo: Path = REPO) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def _repair_id(row: dict[str, Any]) -> str:
    material = "::".join(
        [
            str(row.get("module") or ""),
            str(row.get("repair_bucket") or ""),
            str(row.get("module_path") or ""),
            str(row.get("gold_source_path") or ""),
        ]
    )
    return (
        f"full_dataset::{row.get('module','')}::{row.get('repair_bucket','')}::"
        f"{hashlib.sha256(material.encode('utf-8')).hexdigest()[:12]}"
    )


def _validator_tier(result: Any) -> str:
    return str(getattr(result, "tier", "") or "")


def _validator_partial_credit(result: Any) -> float:
    semantic = getattr(result, "semantic", None)
    return float(getattr(semantic, "partial_credit", 0.0) or 0.0)


def build_pairs(
    *,
    evidence_path: Path = DEFAULT_EVIDENCE,
    validate_spec: Callable[..., Any] = validate_string,
    allowed_tiers: Iterable[str] = ("gold",),
    include_harness: bool = False,
    only_buckets: Iterable[str] = (),
    timeout: int = 30,
    repo: Path = REPO,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evidence_rows = _load_jsonl(evidence_path)
    allowed = tuple(str(tier).strip().lower() for tier in allowed_tiers if str(tier).strip())
    only_bucket_set = {str(bucket).strip() for bucket in only_buckets if str(bucket).strip()}

    rows: list[dict[str, Any]] = []
    excluded_counts: Counter[str] = Counter()
    validated_tier_counts: Counter[str] = Counter()
    kept_by_bucket: Counter[str] = Counter()
    kept_by_gold_source_kind: Counter[str] = Counter()
    candidate_rows = 0

    for row in evidence_rows:
        bucket = str(row.get("repair_bucket") or "")
        if only_bucket_set and bucket not in only_bucket_set:
            continue
        if not row.get("pair_ready"):
            excluded_counts["excluded_not_pair_ready"] += 1
            continue

        candidate_rows += 1
        if bucket == "skip_harness_repair" and not include_harness:
            excluded_counts["excluded_skip_harness_repair"] += 1
            continue

        repaired_spec = str(row.get("repaired_spec") or "").strip()
        if not repaired_spec:
            excluded_counts["excluded_missing_repaired_spec"] += 1
            continue

        module = str(row.get("module") or "Temp").strip() or "Temp"
        result = validate_spec(repaired_spec, module_name=module, timeout=timeout)
        tier = _validator_tier(result).lower()
        validated_tier_counts[tier] += 1
        partial_credit = _validator_partial_credit(result)
        before_score = float(row.get("before_score") or 0.0)

        if tier not in allowed:
            excluded_counts[f"excluded_tier:{tier or 'unknown'}"] += 1
            continue
        if partial_credit <= before_score:
            excluded_counts["excluded_not_improving"] += 1
            continue

        promoted = {
            "repair_id": _repair_id(row),
            "nl": row.get("nl"),
            "broken_spec": row.get("broken_spec"),
            "errors_rendered": row.get("errors_rendered"),
            "verify_summary": row.get("verify_summary"),
            "before_score": before_score,
            "before_raw_score": before_score,
            "repaired_spec": repaired_spec,
            "after_score": partial_credit,
            "after_raw_score": partial_credit,
            "before_diamond": False,
            "after_diamond": tier == "gold",
            "before_phase": f"full_dataset_{bucket}",
            "after_phase": f"validated_{tier}",
            "after_proof_success": tier == "gold",
            "after_model_audit_ok": tier in {"gold", "silver"},
            "after_success": tier in {"gold", "silver"},
            "after_judge_ok": tier == "gold",
            "before_failure_family": bucket,
            "after_failure_family": f"validated_{tier}",
            "module": module,
            "repair_bucket": bucket,
            "repair_priority": row.get("repair_priority"),
            "gold_source_kind": row.get("gold_source_kind"),
            "gold_source_path": row.get("gold_source_path"),
            "gold_source_repo": row.get("gold_source_repo"),
            "prompt_source_kind": row.get("prompt_source_kind"),
            "prompt_source_path": row.get("prompt_source_path"),
            "validated_tier": tier,
            "validated_partial_credit": partial_credit,
            "source_file": _display_path(evidence_path, repo),
        }
        rows.append(promoted)
        kept_by_bucket[bucket] += 1
        kept_by_gold_source_kind[str(row.get("gold_source_kind") or "")] += 1

    rows.sort(key=lambda item: (float(item.get("before_score") or 0.0), str(item.get("repair_id") or "")))
    summary = {
        "schema": "chattla_tla_prover_full_dataset_validated_repair_pairs_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_path": _display_path(evidence_path, repo),
        "candidate_rows": candidate_rows,
        "rows": len(rows),
        "allowed_tiers": list(allowed),
        "include_harness": include_harness,
        "only_buckets": sorted(only_bucket_set),
        "validated_tier_counts": dict(sorted(validated_tier_counts.items())),
        "excluded_counts": dict(sorted(excluded_counts.items())),
        "kept_by_bucket": dict(sorted(kept_by_bucket.items())),
        "kept_by_gold_source_kind": dict(sorted(kept_by_gold_source_kind.items())),
    }
    return rows, summary


def _write_outputs(*, rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    summary_path = out.with_suffix(".summary.json")
    final_summary = dict(summary)
    final_summary["out"] = _display_path(out)
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--allowed-tier", action="append", default=None)
    parser.add_argument("--include-harness", action="store_true")
    parser.add_argument("--only-bucket", action="append", default=None)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    rows, summary = build_pairs(
        evidence_path=args.evidence,
        allowed_tiers=tuple(args.allowed_tier or ("gold",)),
        include_harness=args.include_harness,
        only_buckets=tuple(args.only_bucket or ()),
        timeout=args.timeout,
    )
    final_summary = _write_outputs(rows=rows, summary=summary, out=args.out)
    print(json.dumps({"out": str(args.out), "summary": final_summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
