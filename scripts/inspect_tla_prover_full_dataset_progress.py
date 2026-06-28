#!/usr/bin/env python3
"""Inspect a partial full-dataset smoke run and report where it is in the module order."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.autoprover_smoke import _discover, _discover_from_module_lists, _default_globs


def _load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sample_rows(rows: list[dict], statuses: list[str], limit: int) -> dict[str, list[dict]]:
    by_status: dict[str, list[dict]] = defaultdict(list)
    wanted = set(statuses)
    for row in rows:
        status = row.get("status")
        if status not in wanted or len(by_status[status]) >= limit:
            continue
        tlapm = row.get("tlapm") or {}
        by_status[status].append(
            {
                "module": row.get("module"),
                "module_path": row.get("module_path"),
                "status": status,
                "tier": tlapm.get("tier"),
                "errors": tlapm.get("errors") or [],
                "tlc_error": row.get("tlc_error"),
            }
        )
    return dict(by_status)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--module-list", action="append", type=Path, default=[])
    parser.add_argument("--glob", action="append", dest="globs")
    parser.add_argument("--sample-status", action="append", default=[])
    parser.add_argument("--sample-limit", type=int, default=3)
    args = parser.parse_args()

    if args.module_list:
        paths = _discover_from_module_lists(args.module_list, limit=0)
    else:
        paths = _discover(args.globs or _default_globs(), limit=0)

    rows = _load_rows(args.jsonl)
    completed = len(rows)
    next_module = str(paths[completed]) if completed < len(paths) else None
    payload = {
        "jsonl": str(args.jsonl),
        "rows_completed": completed,
        "discovered_modules": len(paths),
        "remaining": max(len(paths) - completed, 0),
        "next_module": next_module,
        "last_completed_module": rows[-1].get("module_path") if rows else None,
        "last_completed_status": rows[-1].get("status") if rows else None,
        "status_counts": dict(sorted(Counter(row.get("status", "unknown") for row in rows).items())),
    }
    if args.sample_status:
        payload["status_samples"] = _sample_rows(rows, args.sample_status, args.sample_limit)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
