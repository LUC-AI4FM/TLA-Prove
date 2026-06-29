#!/usr/bin/env python3
"""Materialize public AI4FM seed-module lanes around the current autoprover shape."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.autoprover_smoke import _is_candidate

DEFAULT_SOURCE = REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.jsonl"
DEFAULT_CANDIDATES = REPO / "data" / "processed" / "ai4fm_public_seed_prover_candidates_v1.jsonl"
DEFAULT_SHAPE_READY_OUT = REPO / "data" / "processed" / "ai4fm_public_seed_prover_shape_ready_v1.jsonl"
DEFAULT_SHAPE_READY_NOT_SANY_OUT = (
    REPO / "data" / "processed" / "ai4fm_public_seed_prover_shape_ready_not_sany_v1.jsonl"
)


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


def _row_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("repo", "")),
        str(row.get("source_path", "")),
        str(row.get("module", "")),
        str(row.get("content_sha256", "")),
    )


def _sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("module", "")).lower(),
            str(row.get("repo", "")).lower(),
            str(row.get("source_path", "")).lower(),
        ),
    )


def _summary(
    *,
    schema: str,
    source: Path,
    candidate_source: Path,
    rows: list[dict[str, Any]],
    source_rows: int,
    shape_ready_rows: int,
) -> dict[str, Any]:
    by_repo = Counter(str(row.get("repo", "")) for row in rows if row.get("repo"))
    unique_modules = {str(row.get("module", "")) for row in rows if row.get("module")}
    return {
        "schema": schema,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": _display_path(source),
        "candidate_source_path": _display_path(candidate_source),
        "source_rows": source_rows,
        "shape_ready_source_rows": shape_ready_rows,
        "kept_rows": len(rows),
        "unique_modules": len(unique_modules),
        "top_repos": [{"repo": repo, "rows": count} for repo, count in by_repo.most_common(12)],
    }


def _write_jsonl_and_summary(
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    out: Path,
) -> dict[str, Any]:
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


def build_shape_corpora(
    *,
    source: Path,
    candidate_source: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    source_rows = _load_jsonl(source)
    candidate_rows = _load_jsonl(candidate_source)
    candidate_keys = {_row_key(row) for row in candidate_rows}

    shape_ready_rows = _sorted_rows([dict(row) for row in source_rows if _is_candidate(str(row.get("content", "")))])
    repair_target_rows = _sorted_rows([row for row in shape_ready_rows if _row_key(row) not in candidate_keys])

    shape_ready_summary = _summary(
        schema="chattla_ai4fm_public_seed_prover_shape_ready_v1",
        source=source,
        candidate_source=candidate_source,
        rows=shape_ready_rows,
        source_rows=len(source_rows),
        shape_ready_rows=len(shape_ready_rows),
    )
    repair_target_summary = _summary(
        schema="chattla_ai4fm_public_seed_prover_shape_ready_not_sany_v1",
        source=source,
        candidate_source=candidate_source,
        rows=repair_target_rows,
        source_rows=len(source_rows),
        shape_ready_rows=len(shape_ready_rows),
    )
    repair_target_summary["excluded_sany_clean_rows"] = len(candidate_rows)
    return shape_ready_rows, shape_ready_summary, repair_target_rows, repair_target_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--candidate-source", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--shape-ready-out", type=Path, default=DEFAULT_SHAPE_READY_OUT)
    parser.add_argument("--shape-ready-not-sany-out", type=Path, default=DEFAULT_SHAPE_READY_NOT_SANY_OUT)
    args = parser.parse_args()

    shape_ready_rows, shape_ready_summary, repair_rows, repair_summary = build_shape_corpora(
        source=args.source,
        candidate_source=args.candidate_source,
    )
    report = {
        "shape_ready": _write_jsonl_and_summary(
            rows=shape_ready_rows,
            summary=shape_ready_summary,
            out=args.shape_ready_out,
        ),
        "shape_ready_not_sany": _write_jsonl_and_summary(
            rows=repair_rows,
            summary=repair_summary,
            out=args.shape_ready_not_sany_out,
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
