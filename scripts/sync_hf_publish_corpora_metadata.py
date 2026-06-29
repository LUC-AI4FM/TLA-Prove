#!/usr/bin/env python3
"""Sync the public HF corpus bundle metadata from local source artifacts."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.check_public_dataset_claims import BUNDLE_ROOT, _bundled_metadata_sources

DEFAULT_BUNDLE_ROOT = BUNDLE_ROOT


def _display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def build_report(*, repo: Path = REPO, bundle_root: Path = DEFAULT_BUNDLE_ROOT, write: bool = True) -> dict[str, Any]:
    copied: list[dict[str, Any]] = []
    missing_sources: list[str] = []
    metadata_root = bundle_root / "metadata"
    if write:
        metadata_root.mkdir(parents=True, exist_ok=True)

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
