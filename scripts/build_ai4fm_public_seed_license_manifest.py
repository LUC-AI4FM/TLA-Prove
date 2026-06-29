#!/usr/bin/env python3
"""Summarize license/provenance for the committed public AI4FM seed-repo lane."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DISCOVERY = REPO / "data" / "processed" / "ai4fm_public_discovery_manifest_v1.jsonl"
DEFAULT_SEED_SUMMARY = REPO / "data" / "processed" / "ai4fm_public_seed_file_manifest_v1.summary.json"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "ai4fm_public_seed_license_surface.json"

PERMISSIVE_LICENSES = {
    "0BSD",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MIT",
    "Unlicense",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _normalize_license(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    text = str(value).strip()
    return text if text else "UNKNOWN"


def build_report(
    *,
    discovery_rows: list[dict[str, Any]],
    seed_summary: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    per_repo_counts = seed_summary["per_repo"]
    discovery_by_repo = {
        str(row["repo"]): row
        for row in discovery_rows
        if "seed" in row.get("query_hits", []) and row.get("repo")
    }

    repos = []
    missing_discovery = []
    license_repo_counts: Counter[str] = Counter()
    license_tla_counts: Counter[str] = Counter()
    license_all_file_counts: Counter[str] = Counter()

    for repo_name, meta in sorted(per_repo_counts.items()):
        discovery = discovery_by_repo.get(repo_name)
        if discovery is None:
            missing_discovery.append(repo_name)
        license_spdx = _normalize_license(discovery.get("license_spdx") if discovery else None)
        counts = dict(meta["counts"])
        repos.append(
            {
                "repo": repo_name,
                "license_spdx": license_spdx,
                "default_branch": meta["default_branch"],
                "repo_head_sha": meta["repo_head_sha"],
                "counts": counts,
                "html_url": discovery.get("html_url") if discovery else f"https://github.com/{repo_name}",
                "query_hits": discovery.get("query_hits", []) if discovery else [],
                "clearly_permissive_license": license_spdx in PERMISSIVE_LICENSES,
            }
        )
        license_repo_counts[license_spdx] += 1
        license_tla_counts[license_spdx] += int(counts.get("tla", 0))
        license_all_file_counts[license_spdx] += int(counts.get("all", 0))

    caution_repos = [
        repo["repo"]
        for repo in repos
        if not repo["clearly_permissive_license"]
    ]

    return {
        "schema": "chattla_ai4fm_public_seed_license_surface_v1",
        "generated_at": generated_at,
        "sources": {
            "discovery_manifest": str(DEFAULT_DISCOVERY.relative_to(REPO)),
            "seed_file_manifest_summary": str(DEFAULT_SEED_SUMMARY.relative_to(REPO)),
        },
        "seed_repo_inputs": int(seed_summary["seed_repo_inputs"]),
        "tracked_seed_files": int(seed_summary["totals"]["all"]),
        "tracked_tla_files": int(seed_summary["totals"]["tla"]),
        "license_summary": {
            "repo_counts": dict(sorted(license_repo_counts.items())),
            "tracked_tla_file_counts": dict(sorted(license_tla_counts.items())),
            "tracked_file_counts": dict(sorted(license_all_file_counts.items())),
            "clearly_permissive_repo_count": sum(1 for repo in repos if repo["clearly_permissive_license"]),
            "caution_repo_count": len(caution_repos),
        },
        "caution_repos": caution_repos,
        "missing_discovery_records": missing_discovery,
        "repos": repos,
        "notes": [
            "This report joins live-discovery repo metadata with the committed seed file-manifest counts.",
            "Repo-level SPDX labels are a provenance aid, not a file-by-file legal conclusion for every copied artifact.",
            "UNKNOWN and NOASSERTION entries should be treated as redistribution-caution buckets until reviewed separately.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", type=Path, default=DEFAULT_DISCOVERY)
    parser.add_argument("--seed-summary", type=Path, default=DEFAULT_SEED_SUMMARY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report(
        discovery_rows=_read_jsonl(args.discovery),
        seed_summary=_read_json(args.seed_summary),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
