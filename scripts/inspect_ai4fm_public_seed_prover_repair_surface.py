#!/usr/bin/env python3
"""Inspect the shape-ready-but-not-SANY-clean public AI4FM repair surface."""
from __future__ import annotations

import argparse
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
DEFAULT_SOURCE_SUMMARY = REPO / "data" / "processed" / "ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json"
DEFAULT_SEED_MODULES = REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.jsonl"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "ai4fm_public_seed_prover_repair_surface.json"
MAX_TOP_ITEMS = 12
MISSING_IMPORT_RE = re.compile(r"Cannot find source file for module ([A-Za-z0-9_]+) imported in module ([A-Za-z0-9_]+)\.")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _top_counter(counter: Counter[str], *, key_name: str = "name") -> list[dict[str, Any]]:
    return [{key_name: name, "count": count} for name, count in counter.most_common(MAX_TOP_ITEMS)]


def _first_meaningful_error(errors: list[str], raw_output: str) -> str:
    for error in errors:
        if error and not error.startswith("*** Errors:"):
            return error
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Cannot find source file for module "):
            return stripped
        if stripped.startswith("Unknown operator"):
            return stripped
        if stripped.startswith("Expected "):
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


def _availability(module: str, *, row_repo: str, module_to_repos: dict[str, set[str]]) -> str:
    if module == "TLAPS":
        return "tlaps_standard_module"
    repos = module_to_repos.get(module, set())
    if row_repo in repos:
        return "same_repo_seed_module"
    if repos:
        return "cross_repo_seed_module"
    return "missing_from_seed_surface"


def _category(first_error: str, missing_imports: list[str]) -> str:
    if missing_imports:
        return "missing_import"
    lowered = first_error.lower()
    if "unknown operator" in lowered:
        return "unknown_operator"
    if first_error.startswith("Expected ") or "parse" in lowered:
        return "parse_error"
    return "other_sany_invalid"


def build_report(
    *,
    source: Path = DEFAULT_SOURCE,
    source_summary: Path = DEFAULT_SOURCE_SUMMARY,
    seed_modules: Path = DEFAULT_SEED_MODULES,
    helper_source_paths: list[Path] | None = None,
    validate_module: Callable[..., Any] = validate_sany_string,
    validate_file: Callable[..., Any] = validate_sany_file,
    workers: int = 4,
) -> dict[str, Any]:
    source_rows = _load_jsonl(source)
    source_summary_payload = _load_json(source_summary) if source_summary.exists() else None
    seed_rows = _load_jsonl(seed_modules)
    helper_paths = helper_source_paths or []
    helper_rows: list[dict[str, Any]] = []
    for helper_path in helper_paths:
        helper_rows.extend(_load_jsonl(helper_path))
    all_seed_rows = seed_rows + helper_rows

    module_to_repos: dict[str, set[str]] = defaultdict(set)
    for row in all_seed_rows:
        module = str(row.get("module", ""))
        repo = str(row.get("repo", ""))
        if module and repo:
            module_to_repos[module].add(repo)
    by_repo_module, by_module = _build_indexes(all_seed_rows)

    category_counts: Counter[str] = Counter()
    first_error_counts: Counter[str] = Counter()
    repair_rows_by_repo: Counter[str] = Counter()
    missing_import_module_counts: Counter[str] = Counter()
    missing_import_availability_counts: Counter[str] = Counter()
    missing_import_rows = 0
    rows_recoverable_from_seed_surface = 0
    samples: list[dict[str, Any]] = []
    warnings: list[str] = []

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
            first_error = _first_meaningful_error(final_errors, final_raw_output)
            if final_missing_imports:
                missing = list(final_missing_imports)
            elif staged_unresolved:
                missing = list(staged_unresolved)
        availabilities = [_availability(name, row_repo=repo, module_to_repos=module_to_repos) for name in missing]
        category = _category(first_error, missing)
        return {
            "module": module,
            "repo": repo,
            "source_path": row.get("source_path"),
            "first_error": first_error,
            "initial_missing_imports": initial_missing,
            "missing_imports": missing,
            "missing_import_availability": availabilities,
            "staged_modules": staged_modules,
            "category": category,
            "unexpected_valid": bool(getattr(result, "valid", False)),
        }

    max_workers = max(1, workers)
    if max_workers == 1:
        processed = map(process, source_rows)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            processed = executor.map(process, source_rows)

    for item in processed:
        repo = str(item["repo"])
        if repo:
            repair_rows_by_repo[repo] += 1
        if item["unexpected_valid"]:
            warnings.append(f"{item['module']} unexpectedly validated clean during repair-surface inspection")
        category_counts[str(item["category"])] += 1
        first_error_counts[str(item["first_error"])] += 1
        missing = list(item["missing_imports"])
        if missing:
            missing_import_rows += 1
            recoverable = True
            for module, availability in zip(missing, item["missing_import_availability"], strict=True):
                missing_import_module_counts[module] += 1
                missing_import_availability_counts[availability] += 1
                if availability == "missing_from_seed_surface":
                    recoverable = False
            if recoverable:
                rows_recoverable_from_seed_surface += 1
        if len(samples) < MAX_TOP_ITEMS:
            samples.append(item)

    excluded_sany_clean_rows = None
    unique_modules = len({str(row.get("module", "")) for row in source_rows if row.get("module")})
    if source_summary_payload is not None:
        excluded_value = source_summary_payload.get("excluded_sany_clean_rows")
        if isinstance(excluded_value, int):
            excluded_sany_clean_rows = excluded_value
        kept_value = source_summary_payload.get("kept_rows")
        if isinstance(kept_value, int) and kept_value != len(source_rows):
            warnings.append("shape-ready-not-sany summary kept_rows does not match the current repair surface rows")

    return {
        "schema": "chattla_ai4fm_public_seed_prover_repair_surface_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": _display_path(source),
            "summary_path": _display_path(source_summary),
            "rows": len(source_rows),
        },
        "seed_modules": {
            "path": _display_path(seed_modules),
            "rows": len(seed_rows),
            "unique_module_names": len(module_to_repos),
            "helper_source_paths": [_display_path(path) for path in helper_paths],
            "helper_source_rows": len(helper_rows),
        },
        "repair_surface": {
            "rows": len(source_rows),
            "unique_modules": unique_modules,
            "unique_repos": len(repair_rows_by_repo),
            "excluded_sany_clean_rows": excluded_sany_clean_rows,
        },
        "failure_categories": _top_counter(category_counts),
        "top_first_errors": _top_counter(first_error_counts, key_name="error"),
        "missing_imports": {
            "rows_with_missing_imports": missing_import_rows,
            "rows_recoverable_from_seed_surface_or_tlaps_stub": rows_recoverable_from_seed_surface,
            "availability_counts": dict(sorted(missing_import_availability_counts.items())),
            "top_missing_modules": [
                {
                    "module": module,
                    "rows": count,
                    "availability": _availability(module, row_repo="", module_to_repos=module_to_repos),
                }
                for module, count in missing_import_module_counts.most_common(MAX_TOP_ITEMS)
            ],
        },
        "by_repo": {
            "top_repair_repos": _top_counter(repair_rows_by_repo),
        },
        "samples": samples,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--source-summary", type=Path, default=DEFAULT_SOURCE_SUMMARY)
    parser.add_argument("--seed-modules", type=Path, default=DEFAULT_SEED_MODULES)
    parser.add_argument("--helper-source", type=Path, action="append", default=[])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    helper_paths = list(args.helper_source)
    if not helper_paths:
        helper_paths = default_existing_helper_sources()

    report = build_report(
        source=args.source,
        source_summary=args.source_summary,
        seed_modules=args.seed_modules,
        helper_source_paths=helper_paths,
        validate_file=validate_sany_file,
        workers=args.workers,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
