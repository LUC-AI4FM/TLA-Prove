#!/usr/bin/env python3
"""Build a compact failure-analysis manifest from a full-dataset autoprover smoke run."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.summarize_autoprover_smoke import _load_rows, _skip_reason_family, _tlc_error_family, summarize

DEFAULT_JSONL = REPO / "outputs" / "autoprover" / "full_dataset_smoke_161031.jsonl"
DEFAULT_SUMMARY = REPO / "outputs" / "autoprover" / "full_dataset_smoke_161031.summary.json"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_failure_analysis.json"

ACTION_BUCKETS = {
    "proof_replay_ready": "Inductiveness/harness now passes; rerun with a TLAPS-enabled environment to collect proof outcomes.",
    "proof_repair": "TLAPS partials: best immediate repair/training evidence.",
    "inductiveness_repair": "TLC counterexample rows: useful for invariant/repair loops.",
    "tlc_repair": "Verifier/runtime failures that need TLC-side repair or better pre-skips.",
    "skip_harness_repair": "Skips caused by bounded-domain or harness-shape gaps.",
    "skip_missing_contract": "Rows outside the current autoprover contract (missing Init/Next/Spec/TypeOK/vars).",
    "skip_sany_invalid": "Rows rejected by SANY before proof work begins.",
    "skip_other": "Other skip reasons that still need manual review.",
}


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _action_bucket(row: dict[str, Any]) -> str:
    status = row.get("status")
    if status in {"skeleton_emitted", "no_tlapm"}:
        return "proof_replay_ready"
    if status == "tlaps_partial":
        return "proof_repair"
    if status == "not_inductive":
        return "inductiveness_repair"
    if status == "tlc_error":
        return "tlc_repair"
    if status != "skipped":
        return "skip_other"
    family = _skip_reason_family(str(row.get("reason", "")))
    if family == "skip_missing_contract_operators":
        return "skip_missing_contract"
    if family == "skip_sany_parse_or_semantic_invalid":
        return "skip_sany_invalid"
    if family in {
        "skip_unbounded_sequence_domain",
        "skip_init_state_space_too_large",
        "skip_missing_variable_domain",
        "skip_infinite_builtin_domain",
    }:
        return "skip_harness_repair"
    return "skip_other"


def _sample_row(row: dict[str, Any]) -> dict[str, Any]:
    tlapm = row.get("tlapm") or {}
    sample = {
        "module": row.get("module"),
        "module_path": row.get("module_path"),
        "status": row.get("status"),
        "reason": row.get("reason"),
        "runtime_seconds": row.get("runtime_seconds"),
    }
    if row.get("cti_preview"):
        sample["cti_preview"] = str(row["cti_preview"])[:280]
    if row.get("tlc_error"):
        sample["tlc_error_family"] = _tlc_error_family(str(row["tlc_error"]))
        sample["tlc_error"] = str(row["tlc_error"]).splitlines()[0][:280]
    if tlapm:
        sample["tlapm"] = {
            "tier": tlapm.get("tier"),
            "obligations_total": tlapm.get("obligations_total"),
            "obligations_proved": tlapm.get("obligations_proved"),
            "obligations_failed": tlapm.get("obligations_failed"),
        }
    if row.get("sany_errors"):
        sample["sany_errors"] = list(row.get("sany_errors") or [])[:3]
    return sample


def build_failure_analysis(
    *,
    jsonl_path: Path,
    summary_path: Path | None = None,
    sample_limit: int = 5,
) -> dict[str, Any]:
    rows = _load_rows(jsonl_path)
    base = summarize(rows)
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path and summary_path.exists() else None

    bucket_counts = Counter()
    bucket_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tlaps_partial_sorted: list[dict[str, Any]] = []
    for row in rows:
        bucket = _action_bucket(row)
        bucket_counts[bucket] += 1
        if len(bucket_samples[bucket]) < sample_limit:
            bucket_samples[bucket].append(_sample_row(row))
        if row.get("status") == "tlaps_partial":
            tlapm = row.get("tlapm") or {}
            tlaps_partial_sorted.append(
                {
                    "module": row.get("module"),
                    "module_path": row.get("module_path"),
                    "obligations_failed": int(tlapm.get("obligations_failed") or 0),
                    "obligations_proved": int(tlapm.get("obligations_proved") or 0),
                    "obligations_total": int(tlapm.get("obligations_total") or 0),
                    "runtime_seconds": row.get("runtime_seconds"),
                }
            )

    tlaps_partial_sorted.sort(
        key=lambda item: (-item["obligations_failed"], item["module_path"] or "", item["module"] or "")
    )
    priority_order = [
        "proof_replay_ready",
        "proof_repair",
        "inductiveness_repair",
        "tlc_repair",
        "skip_harness_repair",
        "skip_missing_contract",
        "skip_sany_invalid",
        "skip_other",
    ]
    return {
        "schema": "chattla_tla_prover_full_dataset_failure_analysis_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_jsonl": _display_path(jsonl_path),
        "source_summary": _display_path(summary_path) if summary_path else None,
        "job_id": (summary or {}).get("job"),
        "rows": base["rows"],
        "statuses": base["statuses"],
        "skip_reasons": base["skip_reasons"],
        "skip_reason_families": base["skip_reason_families"],
        "tlc_error_families": base["tlc_error_families"],
        "tlc_error_samples": base["tlc_error_samples"],
        "tlaps_checked": base["tlaps_checked"],
        "tlaps_total_obligations": base["tlaps_total_obligations"],
        "tlaps_proved_obligations": base["tlaps_proved_obligations"],
        "tlaps_failed_obligations": base["tlaps_failed_obligations"],
        "action_bucket_descriptions": ACTION_BUCKETS,
        "action_bucket_counts": {key: bucket_counts.get(key, 0) for key in priority_order},
        "action_bucket_samples": {key: bucket_samples.get(key, []) for key in priority_order if bucket_samples.get(key)},
        "immediate_repair_rows": (
            bucket_counts.get("proof_replay_ready", 0)
            + bucket_counts.get("proof_repair", 0)
            + bucket_counts.get("inductiveness_repair", 0)
            + bucket_counts.get("tlc_repair", 0)
            + bucket_counts.get("skip_harness_repair", 0)
        ),
        "top_tlaps_partial_by_failed_obligations": tlaps_partial_sorted[:20],
        "source_prefixes": base["source_prefixes"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sample-limit", type=int, default=5)
    args = parser.parse_args()

    payload = build_failure_analysis(
        jsonl_path=args.jsonl,
        summary_path=args.summary,
        sample_limit=args.sample_limit,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
