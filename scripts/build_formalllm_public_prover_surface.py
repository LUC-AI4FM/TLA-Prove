#!/usr/bin/env python3
"""Join public FormaLLM file-surface metadata with full-dataset prover smoke evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO / "data" / "processed" / "formalllm_public_module_manifest_v1.jsonl"
DEFAULT_SMOKE = REPO / "outputs" / "autoprover" / "full_dataset_smoke_161031.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "formalllm_public_prover_surface_v1.jsonl"
MAX_TOP = 12


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _sample_smoke(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    sample = {
        "status": row.get("status"),
        "reason": row.get("reason"),
        "runtime_seconds": row.get("runtime_seconds"),
    }
    if row.get("tlc_error"):
        sample["tlc_error"] = str(row["tlc_error"]).splitlines()[0][:280]
    tlapm = row.get("tlapm") or {}
    if tlapm:
        sample["tlapm"] = {
            "tier": tlapm.get("tier"),
            "obligations_total": tlapm.get("obligations_total"),
            "obligations_proved": tlapm.get("obligations_proved"),
            "obligations_failed": tlapm.get("obligations_failed"),
        }
    return sample


def build_surface(*, manifest_path: Path, smoke_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_rows = _load_jsonl(manifest_path)
    smoke_rows = _load_jsonl(smoke_path)
    smoke_by_path = {
        str(row.get("module_path", "")): row
        for row in smoke_rows
        if str(row.get("module_path", "")).startswith("data/FormaLLM/data/")
    }

    enriched: list[dict[str, Any]] = []
    category_counts = Counter()
    scanned_category_counts = Counter()
    status_counts = Counter()
    status_by_category: dict[str, Counter[str]] = defaultdict(Counter)
    unscanned_counts = Counter()
    top_skip_reasons = Counter()
    top_tlc_errors = Counter()
    repair_candidate_rows = 0

    for row in manifest_rows:
        path = str(row.get("path", ""))
        category = str(row.get("category", ""))
        smoke = smoke_by_path.get(path) if path.endswith(".tla") else None
        scanned = smoke is not None
        status = str(smoke.get("status", "unscanned")) if smoke else "unscanned"
        category_counts[category] += 1
        if scanned:
            scanned_category_counts[category] += 1
            status_counts[status] += 1
            status_by_category[category][status] += 1
            if status in {"tlaps_partial", "not_inductive", "tlc_error"}:
                repair_candidate_rows += 1
            reason = str(smoke.get("reason", ""))
            if status == "skipped" and reason:
                top_skip_reasons[reason] += 1
            if smoke.get("tlc_error"):
                top_tlc_errors[str(smoke["tlc_error"]).splitlines()[0][:280]] += 1
        else:
            unscanned_counts[category] += 1

        enriched.append(
            {
                **row,
                "scanned_in_full_dataset_smoke": scanned,
                "smoke": _sample_smoke(smoke),
            }
        )

    summary = {
        "schema": "chattla_formalllm_public_prover_surface_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": _display_path(manifest_path),
        "smoke_path": _display_path(smoke_path),
        "kept_rows": len(enriched),
        "category_counts": dict(sorted(category_counts.items())),
        "scanned_category_counts": dict(sorted(scanned_category_counts.items())),
        "unscanned_category_counts": dict(sorted(unscanned_counts.items())),
        "scanned_formalllm_rows": sum(scanned_category_counts.values()),
        "repair_candidate_rows": repair_candidate_rows,
        "status_counts": dict(sorted(status_counts.items())),
        "status_by_category": {
            category: dict(sorted(counter.items()))
            for category, counter in sorted(status_by_category.items())
        },
        "top_skip_reasons": [{"reason": reason, "rows": count} for reason, count in top_skip_reasons.most_common(MAX_TOP)],
        "top_tlc_errors": [{"error": error, "rows": count} for error, count in top_tlc_errors.most_common(MAX_TOP)],
    }
    return enriched, summary


def _write_jsonl_and_summary(*, rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    out.write_text(payload, encoding="utf-8")
    final_summary = dict(summary)
    final_summary["out"] = _display_path(out)
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_summary["summary"] = _display_path(summary_path)
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--smoke", type=Path, default=DEFAULT_SMOKE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_surface(manifest_path=args.manifest, smoke_path=args.smoke)
    report = _write_jsonl_and_summary(rows=rows, summary=summary, out=args.out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
