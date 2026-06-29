#!/usr/bin/env python3
"""Build a SANY-clean public AI4FM seed-module corpus for the current autoprover."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.autoprover_smoke import _is_candidate
from scripts.build_ai4fm_public_seed_tla_modules import _module_name
from scripts.public_tla_helper_sources import default_existing_helper_sources
from src.validators.sany_validator import validate_file as validate_sany_file
from src.validators.sany_validator import validate_string as validate_sany_string

DEFAULT_SOURCE = REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "ai4fm_public_seed_prover_candidates_v1.jsonl"
MAX_SUMMARY_SAMPLES = 12
# Real public proof modules can require long helper chains before SANY reaches the
# first non-import error. Keep this bounded, but high enough to cover the current
# public seed surface without silently truncating recoverable rows.
MAX_IMPORT_STAGING_ROUNDS = 16
MISSING_IMPORT_RE = re.compile(r"Cannot find source file for module ([A-Za-z0-9_]+) imported in module ([A-Za-z0-9_]+)\.")
TLAPS_STUB = """---- MODULE TLAPS ----
PTL == TRUE
Zenon == TRUE
SMT == TRUE
Isabelle == TRUE
====\n"""

COMMUNITY_UTILITY_MODULES = {
    "FiniteSetsExt",
    "Folds",
    "FunctionTheorems",
    "Functions",
    "Graphs",
    "Relation",
    "SequencesExt",
}


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


def _missing_imports(raw_output: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in MISSING_IMPORT_RE.finditer(raw_output):
        module = match.group(1)
        if module not in seen:
            seen.add(module)
            ordered.append(module)
    return ordered


def _build_indexes(
    source_rows: list[dict[str, Any]],
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    by_repo_module: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_module: dict[str, list[dict[str, Any]]] = {}
    for row in source_rows:
        repo = str(row.get("repo", ""))
        module = str(row.get("module", ""))
        if module and isinstance(row.get("content"), str):
            if repo:
                by_repo_module.setdefault((repo, module), []).append(row)
            by_module.setdefault(module, []).append(row)
    return by_repo_module, by_module


def _path_tokens(path: str) -> set[str]:
    tokens: set[str] = set()
    for part in Path(path).parts:
        for raw in re.split(r"[^A-Za-z0-9]+", part):
            token = raw.lower()
            if token:
                tokens.add(token)
    return tokens


def _path_overlap(path: str, row_source_path: str) -> set[str]:
    ignored = {
        "tla",
        "cfg",
        "specifications",
        "examples",
        "example",
        "modules",
        "tests",
        "test",
        "org",
        "lamport",
        "tlatools",
    }
    return (_path_tokens(path) & _path_tokens(row_source_path)) - ignored


def _shared_prefix_depth(path: str, row_source_path: str) -> int:
    depth = 0
    for left, right in zip(Path(path).parts, Path(row_source_path).parts):
        if left.lower() != right.lower():
            break
        depth += 1
    return depth


def _candidate_rank(candidate: dict[str, Any], *, row_repo: str, row_source_path: str) -> tuple[int, str, str]:
    repo = str(candidate.get("repo", ""))
    path = str(candidate.get("source_path", ""))
    score = 0
    if repo == row_repo:
        score += 100
    if "/modules/" in path or path.startswith("modules/"):
        score += 30
    if "CommunityModules" in repo:
        score += 20
    if "__rewire_" in path:
        score -= 50
    if "/tests/" in path or "/.smoke/" in path:
        score -= 10
    overlap = _path_overlap(path, row_source_path)
    score += 5 * len(overlap)
    score += 3 * _shared_prefix_depth(path, row_source_path)
    if Path(path).stem.lower() == Path(row_source_path).stem.lower():
        score += 5
    return score, repo, path


def _resolve_import(
    module: str,
    *,
    row_repo: str,
    row_source_path: str,
    by_repo_module: dict[tuple[str, str], list[dict[str, Any]]],
    by_module: dict[str, list[dict[str, Any]]],
) -> str | None:
    if module == "TLAPS":
        tlapm_standard = by_repo_module.get(("tlaplus/tlapm", "TLAPS"), [])
        if tlapm_standard:
            ranked_tlapm = sorted(
                (row for row in tlapm_standard if isinstance(row.get("content"), str)),
                key=lambda row: _candidate_rank(row, row_repo=row_repo, row_source_path=row_source_path),
                reverse=True,
            )
            if ranked_tlapm:
                return str(ranked_tlapm[0].get("content"))
    same_repo_candidates = by_repo_module.get((row_repo, module), [])
    if same_repo_candidates:
        ranked_same_repo = sorted(
            (row for row in same_repo_candidates if isinstance(row.get("content"), str)),
            key=lambda row: _candidate_rank(row, row_repo=row_repo, row_source_path=row_source_path),
            reverse=True,
        )
        if ranked_same_repo:
            best_same_repo = ranked_same_repo[0]
            best_same_repo_overlap = _path_overlap(str(best_same_repo.get("source_path", "")), row_source_path)
            if (
                module in COMMUNITY_UTILITY_MODULES
                and not best_same_repo_overlap
                and any(str(row.get("repo", "")) == "tlaplus/CommunityModules" for row in by_module.get(module, []))
            ):
                ranked_global = sorted(
                    (row for row in by_module.get(module, []) if isinstance(row.get("content"), str)),
                    key=lambda row: _candidate_rank(row, row_repo="", row_source_path=row_source_path),
                    reverse=True,
                )
                if ranked_global:
                    return str(ranked_global[0].get("content"))
            return str(ranked_same_repo[0].get("content"))
    candidates = by_module.get(module, [])
    if not candidates:
        return TLAPS_STUB if module == "TLAPS" else None
    ranked = sorted(
        (row for row in candidates if isinstance(row.get("content"), str)),
        key=lambda row: _candidate_rank(row, row_repo=row_repo, row_source_path=row_source_path),
        reverse=True,
    )
    if not ranked:
        return TLAPS_STUB if module == "TLAPS" else None
    return str(ranked[0].get("content"))


def _validate_with_staged_imports(
    row: dict[str, Any],
    *,
    initial_result: Any,
    validate_file: Callable[..., Any],
    by_repo_module: dict[tuple[str, str], list[dict[str, Any]]],
    by_module: dict[str, list[dict[str, Any]]],
    initial_missing_imports: list[str],
) -> tuple[Any, dict[str, Any]]:
    module = str(row.get("module", ""))
    repo = str(row.get("repo", ""))
    content = str(row.get("content", ""))
    staged_modules: dict[str, str] = {module: content}
    unresolved: list[str] = []
    attempted = False

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        pending = list(initial_missing_imports)
        last_result = None
        for _round in range(MAX_IMPORT_STAGING_ROUNDS):
            added = False
            for missing in pending:
                if missing in staged_modules:
                    continue
                resolved = _resolve_import(
                    missing,
                    row_repo=repo,
                    row_source_path=str(row.get("source_path", "")),
                    by_repo_module=by_repo_module,
                    by_module=by_module,
                )
                if resolved is None:
                    unresolved.append(missing)
                    continue
                staged_modules[missing] = resolved
                added = True
                attempted = True
            if not added:
                break
            for staged_module, staged_content in staged_modules.items():
                (root / f"{staged_module}.tla").write_text(staged_content, encoding="utf-8")
            last_result = validate_file(root / f"{module}.tla")
            if getattr(last_result, "valid", False):
                return last_result, {
                    "attempted": attempted,
                    "recovered": True,
                    "staged_modules": sorted(name for name in staged_modules if name != module),
                    "unresolved_missing_imports": sorted(set(unresolved)),
                }
            pending = _missing_imports(str(getattr(last_result, "raw_output", "")))
            if not pending:
                break

    if last_result is None:
        return initial_result, {
            "attempted": False,
            "recovered": False,
            "staged_modules": [],
            "unresolved_missing_imports": sorted(set(initial_missing_imports)),
            "final_missing_imports": sorted(set(initial_missing_imports)),
        }
    final_missing_imports = _missing_imports(str(getattr(last_result, "raw_output", "")))
    return last_result, {
        "attempted": attempted,
        "recovered": False,
        "staged_modules": sorted(name for name in staged_modules if name != module),
        "unresolved_missing_imports": sorted(set(unresolved)),
        "final_missing_imports": final_missing_imports,
    }


def build_prover_candidates(
    source_path: Path,
    *,
    validate_module: Callable[..., Any] = validate_sany_string,
    validate_file: Callable[..., Any] = validate_sany_file,
    generated_at: str | None = None,
    limit: int = 0,
    workers: int = 4,
    source_label: str | None = None,
    helper_source_paths: list[Path] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _load_jsonl(source_path)
    selected_rows = source_rows[:limit] if limit else source_rows
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    helper_paths = helper_source_paths or []
    helper_rows: list[dict[str, Any]] = []
    for helper_path in helper_paths:
        helper_rows.extend(_load_jsonl(helper_path))
    by_repo_module, by_module = _build_indexes(source_rows + helper_rows)

    kept_rows: list[dict[str, Any]] = []
    duplicate_modules: Counter[str] = Counter()
    skipped = Counter()
    sample_invalid: list[dict[str, Any]] = []
    sample_not_candidate: list[dict[str, Any]] = []
    sample_recovered: list[dict[str, Any]] = []
    dependency_staging_attempted = 0
    dependency_staging_recovered = 0

    def process(row: dict[str, Any]) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
        content = row.get("content")
        if not isinstance(content, str) or not _module_name(content):
            return "missing_module_content", None, _sample_entry(row, "missing_module_content")

        module = row.get("module")
        if not isinstance(module, str) or not module:
            return "missing_module_name", None, _sample_entry(row, "missing_module_name")

        sany = validate_module(content, module_name=module)
        if not getattr(sany, "valid", False):
            missing_imports = _missing_imports(str(getattr(sany, "raw_output", "")))
            staged_info = {"attempted": False, "recovered": False, "staged_modules": [], "unresolved_missing_imports": []}
            if missing_imports:
                sany, staged_info = _validate_with_staged_imports(
                    row,
                    initial_result=sany,
                    validate_file=validate_file,
                    by_repo_module=by_repo_module,
                    by_module=by_module,
                    initial_missing_imports=missing_imports,
                )
            if getattr(sany, "valid", False):
                if not _is_candidate(content):
                    sample = _sample_entry(row, "not_autoprover_candidate")
                    if staged_info["attempted"]:
                        sample["staged_modules"] = staged_info["staged_modules"]
                        sample["unresolved_missing_imports"] = staged_info["unresolved_missing_imports"]
                    return "not_autoprover_candidate", None, sample
                payload = dict(row)
                if staged_info["attempted"]:
                    payload["dependency_staging"] = {
                        "staged_modules": staged_info["staged_modules"],
                    }
                return "ok", payload, {
                    "reason": "dependency_staging_recovered" if staged_info["attempted"] else "direct_valid",
                    "staged_modules": staged_info["staged_modules"],
                    "unresolved_missing_imports": staged_info["unresolved_missing_imports"],
                }

            first_error = None
            errors = getattr(sany, "errors", None)
            if isinstance(errors, list) and errors:
                first_error = str(errors[0])
            sample = _sample_entry(row, "sany_invalid", first_error)
            if staged_info["attempted"]:
                sample["staged_modules"] = staged_info["staged_modules"]
                sample["unresolved_missing_imports"] = staged_info["unresolved_missing_imports"]
            return "sany_invalid", None, sample

        if not _is_candidate(content):
            return "not_autoprover_candidate", None, _sample_entry(row, "not_autoprover_candidate")

        return "ok", dict(row), {"reason": "direct_valid", "staged_modules": [], "unresolved_missing_imports": []}

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
            if sample and sample.get("reason") == "dependency_staging_recovered":
                dependency_staging_attempted += 1
                dependency_staging_recovered += 1
                if len(sample_recovered) < MAX_SUMMARY_SAMPLES:
                    sample_recovered.append(
                        {
                            "module": payload.get("module"),
                            "repo": payload.get("repo"),
                            "source_path": payload.get("source_path"),
                            "reason": "dependency_staging_recovered",
                            "staged_modules": sample.get("staged_modules", []),
                        }
                    )
            continue
        skipped[status] += 1
        if sample is None:
            continue
        if sample.get("staged_modules"):
            dependency_staging_attempted += 1
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
        "source_path": source_label or _display_path(source_path),
        "source_rows": len(source_rows),
        "helper_source_paths": [_display_path(path) for path in helper_paths],
        "helper_source_rows": len(helper_rows),
        "rows_considered": len(selected_rows),
        "kept_rows": len(kept_rows),
        "skipped": dict(skipped),
        "duplicate_modules": {name: count for name, count in sorted(duplicate_modules.items()) if count > 1},
        "sample_sany_invalid": sample_invalid,
        "sample_not_autoprover_candidate": sample_not_candidate,
        "dependency_staging": {
            "attempted_rows": dependency_staging_attempted,
            "recovered_rows": dependency_staging_recovered,
            "sample_recovered": sample_recovered,
        },
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
    parser.add_argument("--source-label", default=None)
    parser.add_argument("--helper-source", type=Path, action="append", default=[])
    args = parser.parse_args()
    helper_paths = list(args.helper_source)
    if not helper_paths:
        helper_paths = default_existing_helper_sources()

    rows, summary = build_prover_candidates(
        args.source,
        generated_at=None,
        limit=args.limit,
        workers=args.workers,
        source_label=args.source_label,
        helper_source_paths=helper_paths,
    )
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
