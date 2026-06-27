#!/usr/bin/env python3
"""Summarize autoprover smoke JSONL output for proof/model planning."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def _load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(rows: list[dict]) -> dict:
    statuses = Counter(row.get("status", "unknown") for row in rows)
    reasons = Counter(row.get("reason", "") for row in rows if row.get("reason"))
    by_module_path = Counter(str(Path(row.get("module_path", "")).parts[0:2]) for row in rows)

    tlaps = []
    for row in rows:
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
        "source_prefixes": dict(by_module_path.most_common(20)),
        "tlaps_checked": len(tlaps),
        "tlaps_total_obligations": sum(item["total"] or 0 for item in tlaps),
        "tlaps_proved_obligations": sum(item["proved"] or 0 for item in tlaps),
        "tlaps_failed_obligations": sum(item["failed"] or 0 for item in tlaps),
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
