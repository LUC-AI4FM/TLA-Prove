#!/usr/bin/env python3
"""Build a narrow SFT corpus from specs with verified SANY/TLC Diamond evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.validators.tlc_validator import _extract_constant_names, _infer_constant_type

DEFAULT_SOURCE = REPO / "outputs" / "diamond_gen" / "diamond_generated.jsonl"
DEFAULT_HOLDOUT = REPO / "data" / "processed" / "diamond_eval_holdout.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "sany_tlc_pass_sft_v1.jsonl"

DEVELOPER_PROMPT = """You are ChatTLA, an expert at writing verified TLA+ formal specifications.
When asked to write a TLA+ spec, follow these rules exactly:
1. Start the module with ---- MODULE <ModuleName> ----
2. End with ====
3. Include EXTENDS, VARIABLES, Init, Next, and Spec operators
4. After the TLA+ module, append a TLC configuration block:
   SPECIFICATION Spec
   INVARIANT TypeOK   (if TypeOK is defined)
5. Output only valid TLA+ code. No markdown fences, no explanation outside the spec.
Reasoning: medium"""


def _with_tlc_config(spec: str) -> str:
    if "SPECIFICATION Spec" in spec:
        return spec
    body = spec.rstrip()
    config = ["", "SPECIFICATION Spec"]
    if re.search(r"(?m)^\s*TypeOK\s*==", spec):
        config.append("INVARIANT TypeOK")
    for name in _extract_constant_names(spec):
        config.append(_infer_constant_type(name, spec))
    return body + "\n" + "\n".join(config) + "\n"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _is_verified_pass(row: dict[str, Any]) -> bool:
    return (
        row.get("is_diamond") is True
        and row.get("sany_pass") is True
        and row.get("tier") == "gold"
        and row.get("mutation_caught") is True
        and row.get("trivial_invariant") is False
    )


def _record(row: dict[str, Any]) -> dict[str, Any]:
    module = row["module"]
    return {
        "_tier": "sany_tlc_pass",
        "_source": "diamond_generated_verified",
        "_module": module,
        "_prompt_id": f"diamond_generated/{module}",
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


def build_rows(source: Path, holdout: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _load_jsonl(source)
    holdout_modules = {row.get("module") for row in _load_jsonl(holdout) if row.get("module")}
    rows = []
    skipped_holdout = 0
    skipped_not_pass = 0

    for row in sorted(source_rows, key=lambda item: item.get("module", "")):
        module = row.get("module")
        if module in holdout_modules:
            skipped_holdout += 1
            continue
        if not _is_verified_pass(row):
            skipped_not_pass += 1
            continue
        rows.append(_record(row))

    summary = {
        "source": str(source),
        "holdout": str(holdout),
        "source_rows": len(source_rows),
        "holdout_modules": len(holdout_modules),
        "kept_rows": len(rows),
        "skipped_holdout": skipped_holdout,
        "skipped_not_verified_pass": skipped_not_pass,
        "modules": [row["_module"] for row in rows],
    }
    return rows, summary


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    final_summary = dict(summary)
    final_summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    final_summary["out"] = str(out)
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_summary["summary"] = str(summary_path)
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_rows(args.source, args.holdout)
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
