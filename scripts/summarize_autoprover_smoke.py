#!/usr/bin/env python3
"""Summarize autoprover smoke JSONL output for proof/model planning."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def _load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


_MISSING_IDENTIFIER_RE = re.compile(r"identifier\s+([A-Za-z_]\w*)\s+is either undefined or not an operator", re.IGNORECASE)


def _tlc_error_family(message: str) -> str:
    msg = (message or "").lower()
    if "timed out after 60s" in msg and "init-as-predicate state space too large" in msg:
        return "tlc_error_init_state_space_timeout"
    if "***parse error***" in msg or "parsing or semantic analysis failed" in msg:
        return "tlc_error_parse_or_semantic"
    if "constant parameter" in msg and "is not assigned a value" in msg:
        return "tlc_error_unassigned_constant"
    if "current state is not a legal state" in msg:
        return "tlc_error_illegal_init_state"
    if "tlc produced no conclusive result" in msg and "deadlock reached" in msg:
        return "tlc_error_deadlock"
    if "tlc produced no conclusive result" in msg:
        return "tlc_error_no_conclusive_result"
    missing = _MISSING_IDENTIFIER_RE.search(message or "")
    if missing:
        return f"tlc_error_missing_identifier:{missing.group(1)}"
    return "tlc_error_other"


def _skip_reason_family(reason: str) -> str:
    if reason == "missing_init_next_spec_typeok_vars":
        return "skip_missing_contract_operators"
    if reason == "sany_parse_or_semantic_invalid":
        return "skip_sany_parse_or_semantic_invalid"
    if reason == "typeok_uses_unbounded_seq":
        return "skip_unbounded_sequence_domain"
    if reason == "typeok_init_state_space_too_large":
        return "skip_init_state_space_too_large"
    if reason.startswith("typeok_missing_variable_domain_"):
        return "skip_missing_variable_domain"
    if reason.startswith("typeok_infinite_builtin_domain_"):
        return "skip_infinite_builtin_domain"
    if reason:
        return "skip_other_reason"
    return "skip_without_reason"


def summarize(rows: list[dict]) -> dict:
    statuses = Counter(row.get("status", "unknown") for row in rows)
    reasons = Counter(row.get("reason", "") for row in rows if row.get("reason"))
    reason_families = Counter(
        _skip_reason_family(str(row.get("reason", ""))) for row in rows if row.get("status") == "skipped"
    )
    by_module_path = Counter(str(Path(row.get("module_path", "")).parts[0:2]) for row in rows)
    tlc_error_families = Counter()
    tlc_error_samples: dict[str, list[dict]] = defaultdict(list)

    tlaps = []
    for row in rows:
        if row.get("status") == "tlc_error":
            family = _tlc_error_family(row.get("tlc_error", ""))
            tlc_error_families[family] += 1
            if len(tlc_error_samples[family]) < 3:
                tlc_error_samples[family].append(
                    {
                        "module": row.get("module"),
                        "module_path": row.get("module_path"),
                        "tlc_error": row.get("tlc_error", "")[:280],
                    }
                )
        result = row.get("tlapm") or {}
        if result:
            tlaps.append(
                {
                    "module": row.get("module"),
                    "module_path": row.get("module_path"),
                    "status": row.get("status"),
                    "tier": result.get("tier"),
                    "proved": result.get("obligations_proved", 0),
                    "total": result.get("obligations_total", 0),
                    "failed": result.get("obligations_failed", 0),
                    "errors": result.get("errors", []),
                }
            )

    tlaps_by_status: dict[str, list[dict]] = defaultdict(list)
    for item in tlaps:
        tlaps_by_status[item["status"]].append(item)

    return {
        "rows": len(rows),
        "statuses": dict(sorted(statuses.items())),
        "skip_reasons": dict(reasons.most_common(20)),
        "skip_reason_families": dict(reason_families.most_common(20)),
        "source_prefixes": dict(by_module_path.most_common(20)),
        "tlaps_checked": len(tlaps),
        "tlaps_total_obligations": sum(item["total"] or 0 for item in tlaps),
        "tlaps_proved_obligations": sum(item["proved"] or 0 for item in tlaps),
        "tlaps_failed_obligations": sum(item["failed"] or 0 for item in tlaps),
        "tlc_error_families": dict(tlc_error_families.most_common(20)),
        "tlc_error_samples": dict(tlc_error_samples),
        "tlaps_by_status": {
            status: items[:25] for status, items in sorted(tlaps_by_status.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    rows = _load_rows(args.jsonl)
    summary = summarize(rows)
    text = json.dumps(summary, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
