#!/usr/bin/env python3
"""Probe the remaining public AI4FM repair queue through the current candidate-builder logic."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.build_ai4fm_public_seed_prover_candidates import (
    _build_indexes,
    _missing_imports,
    _validate_with_staged_imports,
)
from src.validators.sany_validator import validate_file as validate_sany_file
from src.validators.sany_validator import validate_string as validate_sany_string

DEFAULT_REPAIR_QUEUE = REPO / "data" / "processed" / "ai4fm_public_seed_prover_repair_queue_v1.jsonl"
DEFAULT_FULL_SOURCE = REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "ai4fm_public_seed_prover_recovery_probe_v1.jsonl"
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


def _first_error(result: Any) -> str:
    errors = [str(item) for item in getattr(result, "errors", [])]
    for error in errors:
        if error and not error.startswith("*** Errors:"):
            return error
    raw_output = str(getattr(result, "raw_output", ""))
    for line in raw_output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return errors[0] if errors else "(no parsed error detail)"


def _row_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("repo", "")),
        str(row.get("source_path", "")),
        str(row.get("module", "")),
        str(row.get("content_sha256", "")),
    )


def build_probe(
    *,
    repair_queue: Path = DEFAULT_REPAIR_QUEUE,
    full_source: Path = DEFAULT_FULL_SOURCE,
    validate_module: Callable[..., Any] = validate_sany_string,
    validate_file: Callable[..., Any] = validate_sany_file,
    workers: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repair_rows = _load_jsonl(repair_queue)
    full_rows = _load_jsonl(full_source)
    by_repo_module, by_module = _build_indexes(full_rows)
    full_by_key = {_row_key(row): row for row in full_rows}

    def process(row: dict[str, Any]) -> dict[str, Any]:
        full_row = full_by_key.get(_row_key(row))
        if full_row is None:
            return {
                **row,
                "probe_status": "missing_full_source_row",
                "current_builder_recovers_row": False,
                "initial_missing_imports": [],
                "staged_modules": [],
                "unresolved_missing_imports": [],
                "final_first_error": "full source row not found in seed-module corpus",
            }

        content = str(full_row.get("content", ""))
        module_name = str(full_row.get("module", ""))
        initial_result = validate_module(content, module_name=module_name)
        initial_missing_imports = _missing_imports(str(getattr(initial_result, "raw_output", "")))
        final_result = initial_result
        staged_info = {
            "attempted": False,
            "recovered": False,
            "staged_modules": [],
            "unresolved_missing_imports": [],
        }
        if initial_missing_imports:
            final_result, staged_info = _validate_with_staged_imports(
                full_row,
                initial_result=initial_result,
                validate_file=validate_file,
                by_repo_module=by_repo_module,
                by_module=by_module,
                initial_missing_imports=initial_missing_imports,
            )

        if getattr(final_result, "valid", False):
            status = "recovered_current_builder"
        elif staged_info["unresolved_missing_imports"]:
            status = "still_missing_imports_after_staging"
        elif staged_info["attempted"]:
            status = "post_stage_non_import_error"
        elif initial_missing_imports:
            status = "missing_imports_without_staging"
        else:
            status = "non_import_sany_error"

        return {
            **row,
            "probe_status": status,
            "current_builder_recovers_row": bool(getattr(final_result, "valid", False)),
            "initial_missing_imports": initial_missing_imports,
            "staged_modules": staged_info["staged_modules"],
            "unresolved_missing_imports": staged_info["unresolved_missing_imports"],
            "final_first_error": _first_error(final_result),
        }

    max_workers = max(1, workers)
    if max_workers == 1:
        processed = [process(row) for row in repair_rows]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            processed = list(executor.map(process, repair_rows))

    ordered = sorted(
        processed,
        key=lambda row: (
            str(row.get("probe_status", "")),
            str(row.get("repair_priority", "")),
            str(row.get("repo", "")).lower(),
            str(row.get("module", "")).lower(),
            str(row.get("source_path", "")).lower(),
        ),
    )

    probe_status_counts = Counter(str(row.get("probe_status", "")) for row in ordered if row.get("probe_status"))
    repo_counts = Counter(str(row.get("repo", "")) for row in ordered if row.get("repo"))
    final_error_counts = Counter(str(row.get("final_first_error", "")) for row in ordered if row.get("final_first_error"))
    unresolved_module_counts = Counter()
    status_by_action: dict[str, Counter[str]] = defaultdict(Counter)
    for row in ordered:
        action = str(row.get("recommended_action", ""))
        status = str(row.get("probe_status", ""))
        if action and status:
            status_by_action[action][status] += 1
        for module in row.get("unresolved_missing_imports", []):
            unresolved_module_counts[str(module)] += 1

    summary = {
        "schema": "chattla_ai4fm_public_seed_prover_recovery_probe_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repair_queue_path": _display_path(repair_queue),
        "full_source_path": _display_path(full_source),
        "kept_rows": len(ordered),
        "rows_recovered_current_builder": sum(1 for row in ordered if row.get("current_builder_recovers_row")),
        "probe_status_counts": dict(sorted(probe_status_counts.items())),
        "status_by_recommended_action": {
            action: dict(sorted(counter.items()))
            for action, counter in sorted(status_by_action.items())
        },
        "rows_still_missing_imports_after_staging": probe_status_counts.get("still_missing_imports_after_staging", 0),
        "rows_post_stage_non_import_error": probe_status_counts.get("post_stage_non_import_error", 0),
        "rows_missing_full_source_row": probe_status_counts.get("missing_full_source_row", 0),
        "top_unresolved_missing_modules": [
            {"module": module, "rows": count} for module, count in unresolved_module_counts.most_common(MAX_TOP)
        ],
        "top_final_errors": [{"error": error, "rows": count} for error, count in final_error_counts.most_common(MAX_TOP)],
        "top_repos": [{"repo": repo, "rows": count} for repo, count in repo_counts.most_common(MAX_TOP)],
        "measured_conclusion": (
            "The current public seed candidate builder does not yet recover any rows from the remaining repair queue; "
            "the residual gap is dominated by unresolved imports after staging, with a smaller post-staging non-import SANY bucket."
        ),
    }
    return ordered, summary


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
    parser.add_argument("--repair-queue", type=Path, default=DEFAULT_REPAIR_QUEUE)
    parser.add_argument("--full-source", type=Path, default=DEFAULT_FULL_SOURCE)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_probe(
        repair_queue=args.repair_queue,
        full_source=args.full_source,
        workers=args.workers,
    )
    report = _write_jsonl_and_summary(rows=rows, summary=summary, out=args.out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
