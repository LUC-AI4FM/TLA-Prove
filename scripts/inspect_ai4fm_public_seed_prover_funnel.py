#!/usr/bin/env python3
"""Inspect the public AI4FM seed-module prover funnel without re-running SANY."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.autoprover_smoke import _defines, _is_candidate

DEFAULT_SOURCE = REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.jsonl"
DEFAULT_SOURCE_SUMMARY = REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.summary.json"
DEFAULT_CANDIDATES = REPO / "data" / "processed" / "ai4fm_public_seed_prover_candidates_v1.jsonl"
DEFAULT_CANDIDATE_SUMMARY = REPO / "data" / "processed" / "ai4fm_public_seed_prover_candidates_v1.summary.json"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "ai4fm_public_seed_prover_funnel.json"
REQUIRED_OPERATORS = ("Init", "Next", "Spec", "TypeOK")
MAX_TOP_ITEMS = 12
TEMPORAL_SPEC_RE = re.compile(r"Spec\s*==.*\[\]\[Next\]_", re.DOTALL)


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


def _has_vars_shape(src: str) -> bool:
    return _defines(src, "vars") or bool(TEMPORAL_SPEC_RE.search(src))


def _top_counter(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(MAX_TOP_ITEMS)]


def build_report(
    *,
    source: Path = DEFAULT_SOURCE,
    source_summary: Path = DEFAULT_SOURCE_SUMMARY,
    candidates: Path = DEFAULT_CANDIDATES,
    candidate_summary: Path = DEFAULT_CANDIDATE_SUMMARY,
) -> dict[str, Any]:
    source_rows = _load_jsonl(source)
    source_summary_payload = _load_json(source_summary) if source_summary.exists() else None
    candidate_rows = _load_jsonl(candidates) if candidates.exists() else []
    candidate_summary_payload = _load_json(candidate_summary) if candidate_summary.exists() else None

    total_by_repo: Counter[str] = Counter()
    shape_ready_by_repo: Counter[str] = Counter()
    sany_clean_by_repo: Counter[str] = Counter()
    missing_operator_counts: Counter[str] = Counter()
    missing_combo_counts: Counter[str] = Counter()
    shape_ready_unique_modules: set[str] = set()

    for row in candidate_rows:
        repo = str(row.get("repo", ""))
        if repo:
            sany_clean_by_repo[repo] += 1

    shape_ready_rows = 0
    not_shape_ready_rows = 0
    for row in source_rows:
        repo = str(row.get("repo", ""))
        module = str(row.get("module", ""))
        src = str(row.get("content", ""))
        if repo:
            total_by_repo[repo] += 1
        if _is_candidate(src):
            shape_ready_rows += 1
            if repo:
                shape_ready_by_repo[repo] += 1
            if module:
                shape_ready_unique_modules.add(module)
            continue

        not_shape_ready_rows += 1
        missing = [name for name in REQUIRED_OPERATORS if not _defines(src, name)]
        has_vars_shape = _has_vars_shape(src)
        for name in missing:
            missing_operator_counts[name] += 1
        combo = tuple(missing + ([] if has_vars_shape else ["vars_shape"]))
        missing_combo_counts[" + ".join(combo)] += 1

    sany_clean_rows = len(candidate_rows)
    warnings: list[str] = []
    if candidate_summary_payload is not None:
        source_rows_in_summary = candidate_summary_payload.get("source_rows")
        if isinstance(source_rows_in_summary, int) and source_rows_in_summary != len(source_rows):
            warnings.append("candidate summary source_rows does not match the current seed-module source rows")
        kept_rows_in_summary = candidate_summary_payload.get("kept_rows")
        if isinstance(kept_rows_in_summary, int) and kept_rows_in_summary != sany_clean_rows:
            warnings.append("candidate summary kept_rows does not match the current candidate corpus rows")
    if source_summary_payload is not None:
        kept_rows_in_summary = source_summary_payload.get("kept_rows")
        if isinstance(kept_rows_in_summary, int) and kept_rows_in_summary != len(source_rows):
            warnings.append("seed-module summary kept_rows does not match the current seed-module corpus rows")
    if sany_clean_rows > shape_ready_rows:
        warnings.append("SANY-clean candidate rows exceed shape-ready rows, which should not happen")

    per_repo: list[dict[str, Any]] = []
    for repo in sorted(total_by_repo):
        total_rows = total_by_repo[repo]
        shape_rows = shape_ready_by_repo.get(repo, 0)
        sany_rows = sany_clean_by_repo.get(repo, 0)
        per_repo.append(
            {
                "repo": repo,
                "total_rows": total_rows,
                "shape_ready_rows": shape_rows,
                "sany_clean_rows": sany_rows,
                "shape_ready_rate": round(shape_rows / total_rows, 6) if total_rows else 0.0,
                "sany_clean_rate": round(sany_rows / total_rows, 6) if total_rows else 0.0,
            }
        )

    return {
        "schema": "chattla_ai4fm_public_seed_prover_funnel_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": _display_path(source),
            "summary_path": _display_path(source_summary),
            "rows": len(source_rows),
        },
        "candidates": {
            "path": _display_path(candidates),
            "summary_path": _display_path(candidate_summary),
            "rows": sany_clean_rows,
        },
        "shape_requirements": {
            "required_operator_definitions": list(REQUIRED_OPERATORS),
            "requires_vars_or_temporal_spec_shape": True,
        },
        "funnel": {
            "source_rows": len(source_rows),
            "shape_ready_rows": shape_ready_rows,
            "shape_ready_unique_modules": len(shape_ready_unique_modules),
            "shape_ready_but_not_sany_clean_rows": max(shape_ready_rows - sany_clean_rows, 0),
            "sany_clean_rows": sany_clean_rows,
            "not_shape_ready_rows": not_shape_ready_rows,
        },
        "missing_requirement_counts": {
            "operators": dict(sorted(missing_operator_counts.items())),
            "vars_or_temporal_spec_shape": sum(
                count for combo, count in missing_combo_counts.items() if combo.endswith("vars_shape")
            ),
            "top_requirement_combinations": [
                {"requirements": combo.split(" + "), "count": count}
                for combo, count in missing_combo_counts.most_common(MAX_TOP_ITEMS)
            ],
        },
        "by_repo": {
            "top_shape_ready_repos": _top_counter(shape_ready_by_repo),
            "top_sany_clean_repos": _top_counter(sany_clean_by_repo),
            "repos": per_repo,
        },
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--source-summary", type=Path, default=DEFAULT_SOURCE_SUMMARY)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--candidate-summary", type=Path, default=DEFAULT_CANDIDATE_SUMMARY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report(
        source=args.source,
        source_summary=args.source_summary,
        candidates=args.candidates,
        candidate_summary=args.candidate_summary,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
