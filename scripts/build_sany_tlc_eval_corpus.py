#!/usr/bin/env python3
"""Build a held-out SANY/TLC-pass eval corpus from Diamond holdout rows."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.build_sany_tlc_pass_corpus import DEVELOPER_PROMPT, _is_verified_pass, _load_jsonl, _with_tlc_config

DEFAULT_SOURCE = REPO / "data" / "processed" / "diamond_eval_holdout.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "sany_tlc_pass_eval_v1.jsonl"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _record(row: dict[str, Any]) -> dict[str, Any]:
    module = row["module"]
    return {
        "_tier": "sany_tlc_pass_eval",
        "_source": "diamond_eval_holdout_verified",
        "_module": module,
        "_prompt_id": f"diamond_eval_holdout/{module}",
        "_evidence": {
            "sany_pass": row.get("sany_pass"),
            "tier": row.get("tier"),
            "is_diamond": row.get("is_diamond"),
            "distinct_states": row.get("distinct_states"),
            "invariants_checked": row.get("invariants_checked"),
            "mutation_caught": row.get("mutation_caught"),
            "trivial_invariant": row.get("trivial_invariant"),
            "batch": row.get("batch"),
        },
        "messages": [
            {"role": "developer", "content": DEVELOPER_PROMPT},
            {
                "role": "user",
                "content": f"Write a TLA+ specification for the following:\n\n{row['topic_desc']}\n",
            },
            {
                "role": "assistant",
                "channel": "analysis",
                "content": (
                    f"I'll write module {module} with finite state domains, Init, Next, Spec, "
                    "and TypeOK so it parses with SANY and passes TLC."
                ),
            },
            {"role": "assistant", "channel": "final", "content": _with_tlc_config(row["spec"])},
        ],
    }


def build_rows(source: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _load_jsonl(source)
    rows = []
    skipped_not_pass = 0

    for row in sorted(source_rows, key=lambda item: item.get("module", "")):
        if not _is_verified_pass(row):
            skipped_not_pass += 1
            continue
        rows.append(_record(row))

    summary = {
        "source": _display_path(source),
        "source_rows": len(source_rows),
        "kept_rows": len(rows),
        "skipped_not_verified_pass": skipped_not_pass,
        "modules": [row["_module"] for row in rows],
    }
    return rows, summary


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    final_summary = dict(summary)
    final_summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    final_summary["out"] = _display_path(out)
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_summary["summary"] = _display_path(summary_path)
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_rows(args.source)
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
