#!/usr/bin/env python3
"""Materialize assistant-final TLA modules from a processed JSONL corpus."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


_MODULE_RE = re.compile(r"-{4,}\s*MODULE\s+([A-Za-z_]\w*)", re.IGNORECASE)


def _assistant_final(row: dict) -> str | None:
    messages = row.get("messages") or []
    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("channel") == "final":
            content = message.get("content")
            if isinstance(content, str) and "---- MODULE" in content:
                return content
    return None


def _module_name(text: str) -> str | None:
    match = _MODULE_RE.search(text)
    return match.group(1) if match else None


def materialize(
    jsonl_path: Path,
    out_dir: Path,
    *,
    source_filters: set[str] | None = None,
    tier_filters: set[str] | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    seen_names: Counter[str] = Counter()
    written: list[str] = []
    skipped = Counter()
    rows = 0

    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows += 1
        row = json.loads(line)
        source = row.get("_source")
        if source_filters and source not in source_filters:
            skipped["source_filtered"] += 1
            continue
        tier = row.get("_tier")
        if tier_filters and tier not in tier_filters:
            skipped["tier_filtered"] += 1
            continue
        final = _assistant_final(row)
        if not final:
            skipped["missing_assistant_final_module"] += 1
            continue
        module = row.get("_module_name") or _module_name(final)
        if not module:
            skipped["missing_module_name"] += 1
            continue

        ordinal = seen_names[module]
        seen_names[module] += 1
        filename = f"{module}.tla" if ordinal == 0 else f"{module}__{ordinal + 1}.tla"
        path = out_dir / filename
        path.write_text(final.rstrip() + "\n", encoding="utf-8")
        written.append(str(path))

    payload = {
        "jsonl": str(jsonl_path),
        "out_dir": str(out_dir),
        "rows_seen": rows,
        "files_written": len(written),
        "unique_modules": len(seen_names),
        "duplicates": {name: count for name, count in seen_names.items() if count > 1},
        "skipped": dict(skipped),
        "written_files": written,
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--source", action="append", dest="sources", default=[])
    parser.add_argument("--tier", action="append", dest="tiers", default=[])
    parser.add_argument("--summary-out", type=Path)
    args = parser.parse_args()

    payload = materialize(
        args.jsonl,
        args.out_dir,
        source_filters=set(args.sources) if args.sources else None,
        tier_filters=set(args.tiers) if args.tiers else None,
    )
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
