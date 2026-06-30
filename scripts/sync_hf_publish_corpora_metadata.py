#!/usr/bin/env python3
"""Sync the public HF corpus bundle metadata from local source artifacts."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.check_public_dataset_claims import BUNDLE_ROOT, _bundled_data_sources, _bundled_metadata_sources

DEFAULT_BUNDLE_ROOT = BUNDLE_ROOT
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _scrub_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _scrub_public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub_public_value(item) for item in value]
    if isinstance(value, str):
        return EMAIL_RE.sub("<EMAIL>", value)
    return value


def _sanitize_public_row(row: dict[str, Any]) -> dict[str, Any]:
    sanitized = _scrub_public_value(row)
    messages = sanitized.get("messages")
    if isinstance(messages, list):
        sanitized["messages"] = [
            message
            for message in messages
            if not (
                isinstance(message, dict)
                and message.get("role") == "assistant"
                and message.get("channel") == "analysis"
            )
        ]
    return sanitized


def _sanitize_jsonl_bytes(source: Path) -> tuple[bytes, int]:
    lines: list[str] = []
    row_count = 0
    with source.open(encoding="utf-8") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object rows in {_display(source)}")
            sanitized = _sanitize_public_row(row)
            lines.append(json.dumps(sanitized, sort_keys=True) + "\n")
            row_count += 1
    return "".join(lines).encode("utf-8"), row_count


def build_report(*, repo: Path = REPO, bundle_root: Path = DEFAULT_BUNDLE_ROOT, write: bool = True) -> dict[str, Any]:
    copied: list[dict[str, Any]] = []
    missing_sources: list[str] = []
    metadata_root = bundle_root / "metadata"
    data_root = bundle_root / "data"
    if write:
        metadata_root.mkdir(parents=True, exist_ok=True)
        data_root.mkdir(parents=True, exist_ok=True)

    for bundle_name, source_rel in _bundled_metadata_sources(repo).items():
        source = repo / source_rel
        target = metadata_root / bundle_name
        if not source.exists():
            missing_sources.append(source_rel)
            continue
        changed = (not target.exists()) or target.read_bytes() != source.read_bytes()
        if write:
            shutil.copyfile(source, target)
        copied.append(
            {
                "bundle_name": bundle_name,
                "source": source_rel,
                "target": _display(target),
                "changed": changed,
                "bytes": source.stat().st_size,
            }
        )

    for target_rel, source_rel in _bundled_data_sources().items():
        source = repo / source_rel
        target = bundle_root / target_rel
        if not source.exists():
            missing_sources.append(source_rel)
            continue
        payload, row_count = _sanitize_jsonl_bytes(source)
        changed = (not target.exists()) or target.read_bytes() != payload
        if write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        copied.append(
            {
                "bundle_name": Path(target_rel).name,
                "source": source_rel,
                "target": _display(target),
                "changed": changed,
                "bytes": len(payload),
                "rows": row_count,
            }
        )

    return {
        "ok": not missing_sources,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": _display(repo),
        "bundle_root": _display(bundle_root),
        "write": write,
        "copied": copied,
        "missing_sources": missing_sources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--check", action="store_true", help="Report the sync plan without writing files.")
    args = parser.parse_args()

    report = build_report(repo=args.repo, bundle_root=args.bundle_root, write=not args.check)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
