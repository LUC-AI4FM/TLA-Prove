#!/usr/bin/env python3
"""Materialize a prioritized repair queue for the public AI4FM seed prover surface."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.build_ai4fm_public_seed_prover_candidates import _build_indexes, _validate_with_staged_imports
from scripts.public_tla_helper_sources import default_existing_helper_sources
from src.validators.sany_validator import validate_file as validate_sany_file
from src.validators.sany_validator import validate_string as validate_sany_string

DEFAULT_SOURCE = REPO / "data" / "processed" / "ai4fm_public_seed_prover_shape_ready_not_sany_v1.jsonl"
DEFAULT_SEED_MODULES = REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "ai4fm_public_seed_prover_repair_queue_v1.jsonl"
MISSING_IMPORT_RE = re.compile(r"Cannot find source file for module ([A-Za-z0-9_]+) imported in module ([A-Za-z0-9_]+)\.")
MAX_TOP = 12
MAX_CANDIDATE_HELPERS = 6


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


def _first_meaningful_error(errors: list[str], raw_output: str) -> str:
    for error in errors:
        if error and not error.startswith("*** Errors:"):
            return error
    for line in raw_output.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("*** Errors:"):
            return stripped
    return errors[0] if errors else "(no parsed error detail)"


def _missing_imports(raw_output: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in MISSING_IMPORT_RE.finditer(raw_output):
        module = match.group(1)
        if module not in seen:
            seen.add(module)
            ordered.append(module)
    return ordered


def _availability(module: str, *, row_repo: str, module_to_rows: dict[str, list[dict[str, Any]]]) -> str:
    if module == "TLAPS":
        return "tlaps_standard_module"
    candidates = module_to_rows.get(module, [])
    if any(str(item.get("repo", "")) == row_repo for item in candidates):
        return "same_repo_seed_module"
    if candidates:
        return "cross_repo_seed_module"
    return "missing_from_seed_surface"


def _priority_and_action(availabilities: list[str]) -> tuple[str, str, bool]:
    availability_set = set(availabilities)
    if availability_set == {"tlaps_standard_module"}:
        return "p1", "stage_tlaps_standard_module", True
    if availability_set <= {"same_repo_seed_module"}:
        return "p2", "stage_same_repo_seed_helpers", True
    if availability_set <= {"cross_repo_seed_module"}:
        return "p3", "stage_cross_repo_seed_helpers", True
    if availability_set <= {"same_repo_seed_module", "cross_repo_seed_module"}:
        return "p3", "stage_seed_helpers", True
    if "missing_from_seed_surface" in availability_set:
        return "p4", "expand_public_dependency_surface", False
    if availability_set <= {"tlaps_standard_module", "same_repo_seed_module"}:
        return "p2", "stage_tlaps_and_same_repo_helpers", True
    if availability_set <= {"tlaps_standard_module", "cross_repo_seed_module"}:
        return "p3", "stage_tlaps_and_cross_repo_helpers", True
    if availability_set <= {"tlaps_standard_module", "same_repo_seed_module", "cross_repo_seed_module"}:
        return "p3", "stage_tlaps_and_seed_helpers", True
    return "p4", "manual_triage", False


def _helper_rows(module: str, *, module_to_rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    helpers: list[dict[str, Any]] = []
    for row in module_to_rows.get(module, [])[:MAX_CANDIDATE_HELPERS]:
        helpers.append(
            {
                "repo": row.get("repo"),
                "module": row.get("module"),
                "source_path": row.get("source_path"),
                "repo_head_sha": row.get("repo_head_sha"),
            }
        )
    return helpers


def build_queue(
    *,
    source: Path = DEFAULT_SOURCE,
    seed_modules: Path = DEFAULT_SEED_MODULES,
    helper_source_paths: list[Path] | None = None,
    validate_module: Callable[..., Any] = validate_sany_string,
    validate_file: Callable[..., Any] = validate_sany_file,
    workers: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _load_jsonl(source)
    seed_rows = _load_jsonl(seed_modules)
    helper_paths = helper_source_paths or []
    helper_rows: list[dict[str, Any]] = []
    for helper_path in helper_paths:
        helper_rows.extend(_load_jsonl(helper_path))
    all_seed_rows = seed_rows + helper_rows
    module_to_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_seed_rows:
        module = str(row.get("module", ""))
        if module:
            module_to_rows[module].append(row)
    by_repo_module, by_module = _build_indexes(all_seed_rows)

    def process(row: dict[str, Any]) -> dict[str, Any]:
        module = str(row.get("module", ""))
        repo = str(row.get("repo", ""))
        result = validate_module(str(row.get("content", "")), module_name=module)
        errors = [str(item) for item in getattr(result, "errors", [])]
        raw_output = str(getattr(result, "raw_output", ""))
        first_error = _first_meaningful_error(errors, raw_output)
        initial_missing = _missing_imports(raw_output)
        missing = list(initial_missing)
        staged_modules: list[str] = []
        staged_unresolved: list[str] = []
        final_first_error = first_error
        if initial_missing:
            result, staged_info = _validate_with_staged_imports(
                row,
                initial_result=result,
                validate_file=validate_file,
                by_repo_module=by_repo_module,
                by_module=by_module,
                initial_missing_imports=initial_missing,
            )
            staged_modules = list(staged_info.get("staged_modules", []))
            staged_unresolved = list(staged_info.get("unresolved_missing_imports", []))
            final_missing_imports = list(staged_info.get("final_missing_imports", []))
            final_errors = [str(item) for item in getattr(result, "errors", [])]
            final_raw_output = str(getattr(result, "raw_output", ""))
            final_first_error = _first_meaningful_error(final_errors, final_raw_output)
            if final_missing_imports:
                missing = list(final_missing_imports)
            elif staged_unresolved:
                missing = list(staged_unresolved)
        details = []
        availabilities: list[str] = []
        for missing_module in missing:
            availability = _availability(missing_module, row_repo=repo, module_to_rows=module_to_rows)
            availabilities.append(availability)
            details.append(
                {
                    "module": missing_module,
                    "availability": availability,
                    "candidate_helpers": _helper_rows(missing_module, module_to_rows=module_to_rows),
                }
            )
        priority, recommended_action, recoverable = _priority_and_action(availabilities)
        return {
            "repo": row.get("repo"),
            "module": row.get("module"),
            "source_path": row.get("source_path"),
            "content_sha256": row.get("content_sha256"),
            "default_branch": row.get("default_branch"),
            "repo_head_sha": row.get("repo_head_sha"),
            "html_url": row.get("html_url"),
            "download_url": row.get("download_url"),
            "first_error": final_first_error,
            "initial_first_error": first_error,
            "initial_missing_imports": initial_missing,
            "missing_imports": missing,
            "missing_import_details": details,
            "staged_modules": staged_modules,
            "post_stage_unresolved_missing_imports": staged_unresolved,
            "repair_priority": priority,
            "recommended_action": recommended_action,
            "recoverable_without_new_source": recoverable,
        }

    max_workers = max(1, workers)
    if max_workers == 1:
        processed = [process(row) for row in source_rows]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            processed = list(executor.map(process, source_rows))

    ordered = sorted(
        processed,
        key=lambda row: (
            str(row.get("repair_priority", "")),
            str(row.get("recommended_action", "")),
            str(row.get("repo", "")).lower(),
            str(row.get("module", "")).lower(),
            str(row.get("source_path", "")).lower(),
        ),
    )

    priority_counts = Counter(str(row.get("repair_priority", "")) for row in ordered if row.get("repair_priority"))
    action_counts = Counter(str(row.get("recommended_action", "")) for row in ordered if row.get("recommended_action"))
    repo_counts = Counter(str(row.get("repo", "")) for row in ordered if row.get("repo"))
    missing_module_counts = Counter()
    availability_counts = Counter()
    recoverable_rows = 0
    blocked_rows = 0
    for row in ordered:
        if row.get("recoverable_without_new_source"):
            recoverable_rows += 1
        else:
            blocked_rows += 1
        for item in row.get("missing_import_details", []):
            missing_module_counts[str(item.get("module", ""))] += 1
            availability_counts[str(item.get("availability", ""))] += 1

    summary = {
        "schema": "chattla_ai4fm_public_seed_prover_repair_queue_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": _display_path(source),
        "seed_modules_path": _display_path(seed_modules),
        "helper_source_paths": [_display_path(path) for path in helper_paths],
        "helper_source_rows": len(helper_rows),
        "kept_rows": len(ordered),
        "recoverable_without_new_source_rows": recoverable_rows,
        "blocked_on_missing_public_dependency_rows": blocked_rows,
        "priority_counts": dict(sorted(priority_counts.items())),
        "recommended_action_counts": dict(sorted(action_counts.items())),
        "missing_import_availability_counts": dict(sorted(availability_counts.items())),
        "top_missing_modules": [{"module": module, "rows": count} for module, count in missing_module_counts.most_common(MAX_TOP)],
        "top_repos": [{"repo": repo, "rows": count} for repo, count in repo_counts.most_common(MAX_TOP)],
        "stage_plan": [
            {
                "priority": "p1",
                "recommended_action": "stage_tlaps_standard_module",
                "rows": priority_counts.get("p1", 0),
                "note": "Highest-leverage rows: missing only the standard TLAPS helper module.",
            },
            {
                "priority": "p2",
                "recommended_action": "stage_same_repo_seed_helpers",
                "rows": action_counts.get("stage_same_repo_seed_helpers", 0)
                + action_counts.get("stage_tlaps_and_same_repo_helpers", 0),
                "note": "Rows recoverable by staging helper modules already present in the same public repo.",
            },
            {
                "priority": "p3",
                "recommended_action": "stage_cross_repo_seed_helpers",
                "rows": action_counts.get("stage_cross_repo_seed_helpers", 0)
                + action_counts.get("stage_seed_helpers", 0)
                + action_counts.get("stage_tlaps_and_cross_repo_helpers", 0)
                + action_counts.get("stage_tlaps_and_seed_helpers", 0),
                "note": "Rows recoverable by staging helper modules already visible elsewhere in the public seed surface.",
            },
            {
                "priority": "p4",
                "recommended_action": "expand_public_dependency_surface",
                "rows": action_counts.get("expand_public_dependency_surface", 0)
                + action_counts.get("manual_triage", 0),
                "note": "Rows still blocked because at least one required helper module is missing from the current public seed surface.",
            },
        ],
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
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--seed-modules", type=Path, default=DEFAULT_SEED_MODULES)
    parser.add_argument("--helper-source", type=Path, action="append", default=[])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    helper_paths = list(args.helper_source)
    if not helper_paths:
        helper_paths = default_existing_helper_sources()

    rows, summary = build_queue(
        source=args.source,
        seed_modules=args.seed_modules,
        helper_source_paths=helper_paths,
        validate_file=validate_sany_file,
        workers=args.workers,
    )
    report = _write_jsonl_and_summary(rows=rows, summary=summary, out=args.out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
