#!/usr/bin/env python3
"""Replay a selected subset of full-dataset autoprover rows and merge them back into a smoke JSONL."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.autoprover_smoke import progress_summary, run_one, sanitize_public_surface
from scripts.summarize_autoprover_smoke import _load_rows, summarize

DEFAULT_SOURCE = REPO / "outputs" / "autoprover" / "full_dataset_smoke_161031.jsonl"
DEFAULT_OUT = REPO / "outputs" / "autoprover" / "full_dataset_smoke_161031_local_replay.jsonl"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _selected_module_paths(
    rows: list[dict[str, Any]],
    *,
    module_paths: list[str],
    module_names: list[str],
    reasons: list[str],
    statuses: list[str],
) -> list[str]:
    requested_paths = list(dict.fromkeys(module_paths))
    name_set = set(module_names)
    reason_set = set(reasons)
    status_set = set(statuses)
    for row in rows:
        path = str(row.get("module_path") or "")
        if not path:
            continue
        if row.get("module") in name_set:
            requested_paths.append(path)
            continue
        if reason_set and row.get("reason") in reason_set:
            requested_paths.append(path)
            continue
        if status_set and row.get("status") in status_set:
            requested_paths.append(path)
            continue
    unique: list[str] = []
    seen = set()
    for path in requested_paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def replay_subset(
    *,
    source_jsonl: Path,
    module_paths: list[str],
    tlc_timeout: int,
    tlapm_timeout: int,
    run_tlaps: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_rows = _load_rows(source_jsonl)
    selected = set(module_paths)
    replay_rows: list[dict[str, Any]] = []
    replacements: dict[str, dict[str, Any]] = {}
    missing_paths = [path for path in module_paths if not (REPO / path).is_file()]

    for row in source_rows:
        module_path = str(row.get("module_path") or "")
        if module_path not in selected:
            continue
        replay = run_one(
            REPO / module_path,
            tlc_timeout=tlc_timeout,
            tlapm_timeout=tlapm_timeout,
            run_tlaps=run_tlaps,
        )
        replay["replay_source_status"] = row.get("status")
        replay["replay_source_reason"] = row.get("reason")
        replay["replayed_at"] = datetime.now(timezone.utc).isoformat()
        replay = sanitize_public_surface(replay)
        replacements[module_path] = replay
        replay_rows.append(replay)

    merged_rows = sanitize_public_surface([
        replacements.get(str(row.get("module_path") or ""), row)
        for row in source_rows
    ])

    source_statuses = Counter(str(row.get("status") or "unknown") for row in source_rows if str(row.get("module_path") or "") in selected)
    replay_statuses = Counter(str(row.get("status") or "unknown") for row in replay_rows)
    report = sanitize_public_surface({
        "schema": "chattla_tla_prover_full_dataset_subset_replay_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_jsonl": _display_path(source_jsonl),
        "selected_module_paths": module_paths,
        "selected_rows": len(module_paths),
        "replayed_rows": len(replay_rows),
        "missing_paths": missing_paths,
        "source_statuses": dict(sorted(source_statuses.items())),
        "replay_statuses": dict(sorted(replay_statuses.items())),
        "progress": progress_summary(merged_rows),
        "merged_summary": summarize(merged_rows),
        "run_tlaps": run_tlaps,
        "tlc_timeout": tlc_timeout,
        "tlapm_timeout": tlapm_timeout,
    })
    return merged_rows, replay_rows, report


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-jsonl", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Merged JSONL output path.")
    parser.add_argument("--replay-out", type=Path, help="Optional JSONL containing only replayed rows.")
    parser.add_argument("--report-out", type=Path, help="Optional JSON report path.")
    parser.add_argument("--module-path", action="append", default=[], help="Repo-relative .tla path to replay; may be repeated.")
    parser.add_argument("--module", action="append", default=[], help="Module name to replay; matched against source rows.")
    parser.add_argument("--reason", action="append", default=[], help="Replay every row with this source reason.")
    parser.add_argument("--status", action="append", default=[], help="Replay every row with this source status.")
    parser.add_argument("--tlc-timeout", type=int, default=45)
    parser.add_argument("--tlapm-timeout", type=int, default=60)
    parser.add_argument("--skip-tlaps", action="store_true")
    args = parser.parse_args()

    source_rows = _load_rows(args.source_jsonl)
    selected_paths = _selected_module_paths(
        source_rows,
        module_paths=args.module_path,
        module_names=args.module,
        reasons=args.reason,
        statuses=args.status,
    )
    if not selected_paths:
        raise SystemExit("No module paths selected. Use --module-path, --module, --reason, or --status.")

    merged_rows, replay_rows, report = replay_subset(
        source_jsonl=args.source_jsonl,
        module_paths=selected_paths,
        tlc_timeout=args.tlc_timeout,
        tlapm_timeout=args.tlapm_timeout,
        run_tlaps=not args.skip_tlaps,
    )
    _write_jsonl(args.out, merged_rows)
    if args.replay_out:
        _write_jsonl(args.replay_out, replay_rows)
    report_path = args.report_out or args.out.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path = args.out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(report["merged_summary"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
