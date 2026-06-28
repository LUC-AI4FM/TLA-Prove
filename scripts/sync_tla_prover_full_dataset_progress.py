#!/usr/bin/env python3
"""Refresh the tracked full-dataset progress manifest from a partial smoke JSONL."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.autoprover_smoke import _default_globs, _discover, _discover_from_module_lists, progress_summary


def _load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--job-id")
    parser.add_argument("--module-list", action="append", type=Path, default=[])
    parser.add_argument("--glob", action="append", dest="globs")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.module_list:
        discovered_paths = _discover_from_module_lists(args.module_list, limit=0)
    else:
        discovered_paths = _discover(args.globs or _default_globs(), limit=0)

    rows = _load_rows(args.jsonl)
    payload = progress_summary(rows, job_id=args.job_id, discovered_paths=discovered_paths)
    payload["source"] = str(args.jsonl)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
