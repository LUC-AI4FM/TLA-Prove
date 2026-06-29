#!/usr/bin/env python3
"""Build a SANY-clean public AI4FM seed-module corpus for the current autoprover."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.autoprover_smoke import _is_candidate
from src.validators.sany_validator import validate_string as validate_sany_string

DEFAULT_SOURCE = REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "ai4fm_public_seed_prover_candidates_v1.jsonl"
MAX_SUMMARY_SAMPLES = 12


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _sample_entry(row: dict[str, Any], reason: str, detail: str | None = None) -> dict[str, Any]:
    payload = {
        "module": row.get("module"),
        "repo": row.get("repo"),
        "source_path": row.get("source_path"),
        "reason": reason,
    }
    if detail:
        payload["detail"] = detail
    return payload


def build_prover_candidates(
    source_path: Path,
    *,
    validate_module: Callable[..., Any] = validate_sany_string,
    generated_at: str | None = None,
    limit: int = 0,
    workers: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _load_jsonl(source_path)
    selected_rows = source_rows[:limit] if limit else source_rows
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()

    kept_rows: list[dict[str, Any]] = []
    duplicate_modules: Counter[str] = Counter()
    skipped = Counter()
    sample_invalid: list[dict[str, Any]] = []
    sample_not_candidate: list[dict[str, Any]] = []

    def process(row: dict[str, Any]) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
        content = row.get("content")
        if not isinstance(content, str) or "---- MODULE" not in content:
            return "missing_module_content", None, _sample_entry(row, "missing_module_content")

        module = row.get("module")
        if not isinstance(module, str) or not module:
            return "missing_module_name", None, _sample_entry(row, "missing_module_name")

        sany = validate_module(content, module_name=module)
        if not getattr(sany, "valid", False):
            first_error = None
            errors = getattr(sany, "errors", None)
            if isinstance(errors, list) and errors:
                first_error = str(errors[0])
            return "sany_invalid", None, _sample_entry(row, "sany_invalid", first_error)

        if not _is_candidate(content):
            return "not_autoprover_candidate", None, _sample_entry(row, "not_autoprover_candidate")

        return "ok", dict(row), None

    max_workers = max(1, workers)
    if max_workers == 1:
        results = map(process, selected_rows)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = executor.map(process, selected_rows)

    for status, payload, sample in results:
        if status == "ok":
            assert payload is not None
            module = str(payload.get("module"))
            duplicate_modules[module] += 1
            kept_rows.append(payload)
            continue
        skipped[status] += 1
        if sample is None:
            continue
        if status == "sany_invalid" and len(sample_invalid) < MAX_SUMMARY_SAMPLES:
            sample_invalid.append(sample)
        if status == "not_autoprover_candidate" and len(sample_not_candidate) < MAX_SUMMARY_SAMPLES:
            sample_not_candidate.append(sample)

    kept_rows.sort(
        key=lambda row: (
            str(row.get("module", "")).lower(),
            str(row.get("repo", "")).lower(),
            str(row.get("source_path", "")).lower(),
        )
    )
    summary = {
        "schema": "chattla_ai4fm_public_seed_prover_candidates_v1",
        "generated_at": generated_at,
        "source_path": _display_path(source_path),
        "source_rows": len(source_rows),
        "rows_considered": len(selected_rows),
        "kept_rows": len(kept_rows),
        "skipped": dict(skipped),
        "duplicate_modules": {name: count for name, count in sorted(duplicate_modules.items()) if count > 1},
        "sample_sany_invalid": sample_invalid,
        "sample_not_autoprover_candidate": sample_not_candidate,
        "workers": max_workers,
    }
    return kept_rows, summary


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    final_summary = dict(summary)
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
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    rows, summary = build_prover_candidates(
        args.source,
        generated_at=None,
        limit=args.limit,
        workers=args.workers,
    )
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
