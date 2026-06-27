#!/usr/bin/env python3
"""Validate the local SANY/TLC-pass SFT corpus before training."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = REPO / "data" / "processed" / "sany_tlc_pass_sft_v1.jsonl"
DEFAULT_HOLDOUT = REPO / "data" / "processed" / "diamond_eval_holdout.jsonl"
DEFAULT_SUMMARY = REPO / "data" / "processed" / "sany_tlc_pass_sft_v1.summary.json"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "sany_tlc_pass_corpus_diagnostic.json"
MODULE_RE = re.compile(r"----\s+MODULE\s+([A-Za-z_][A-Za-z0-9_]*)\s+----")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _final_content(row: dict[str, Any]) -> str:
    for message in row.get("messages", []):
        if message.get("role") == "assistant" and message.get("channel") == "final":
            return str(message.get("content") or "")
    return ""


def _module_header(text: str) -> str | None:
    match = MODULE_RE.search(text)
    return match.group(1) if match else None


def _weak_evidence(row: dict[str, Any]) -> bool:
    evidence = row.get("_evidence") or {}
    return not (
        row.get("_tier") == "sany_tlc_pass"
        and evidence.get("sany_pass") is True
        and evidence.get("tier") == "gold"
        and evidence.get("is_diamond") is True
        and evidence.get("mutation_caught") is True
        and evidence.get("trivial_invariant") is False
        and int(evidence.get("distinct_states") or 0) >= 2
        and int(evidence.get("invariants_checked") or 0) >= 1
    )


def diagnose_corpus(*, corpus: Path, holdout: Path, summary: Path | None = DEFAULT_SUMMARY) -> dict[str, Any]:
    rows = _load_jsonl(corpus)
    holdout_modules = {row.get("module") for row in _load_jsonl(holdout) if row.get("module")}
    modules = [row.get("_module") for row in rows if row.get("_module")]
    counts = Counter(modules)
    duplicate_modules = sorted(module for module, count in counts.items() if count > 1)
    holdout_overlap = sorted(module for module in modules if module in holdout_modules)
    module_header_mismatches = []
    missing_config_modules = []
    missing_final_modules = []
    weak_evidence_modules = []

    for row in rows:
        module = row.get("_module")
        final = _final_content(row)
        if not module:
            continue
        if not final:
            missing_final_modules.append(module)
            continue
        header = _module_header(final)
        if header != module:
            module_header_mismatches.append(module)
        if "SPECIFICATION Spec" not in final:
            missing_config_modules.append(module)
        if _weak_evidence(row):
            weak_evidence_modules.append(module)

    summary_data = None
    summary_mismatches: list[str] = []
    if summary and summary.exists():
        summary_data = json.loads(summary.read_text(encoding="utf-8"))
        if summary_data.get("kept_rows") != len(rows):
            summary_mismatches.append("kept_rows")
        if summary_data.get("jsonl_sha256") and summary_data.get("jsonl_sha256") != _sha256(corpus):
            summary_mismatches.append("jsonl_sha256")

    failures = {
        "duplicate_modules": duplicate_modules,
        "holdout_overlap": holdout_overlap,
        "module_header_mismatches": sorted(module_header_mismatches),
        "missing_config_modules": sorted(missing_config_modules),
        "missing_final_modules": sorted(missing_final_modules),
        "weak_evidence_modules": sorted(weak_evidence_modules),
        "summary_mismatches": sorted(summary_mismatches),
    }
    ok = all(not value for value in failures.values()) and bool(rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "corpus": str(corpus),
        "holdout": str(holdout),
        "summary": str(summary) if summary else None,
        "rows": len(rows),
        "modules": sorted(modules),
        "jsonl_sha256": _sha256(corpus),
        "summary_data_present": summary_data is not None,
        **failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    payload = diagnose_corpus(corpus=args.corpus, holdout=args.holdout, summary=args.summary)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
