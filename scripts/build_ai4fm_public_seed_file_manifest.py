#!/usr/bin/env python3
"""Materialize the public AI4FM seed-repo file surface from GitHub trees."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.build_ai4fm_public_discovery_manifest import _load_seed_inputs

DEFAULT_PIPELINE_REPO = Path("/tmp/LUC-AI4FM-tla-dataset-pipeline")
DEFAULT_OUT = REPO / "data" / "processed" / "ai4fm_public_seed_file_manifest_v1.jsonl"
TRACKED_EXTENSIONS = (".cfg", ".tla", ".tlaps")


def _gh_api(path: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["gh", "api", path],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def _file_record(repo: str, branch: str, repo_sha: str, item: dict[str, Any]) -> dict[str, Any]:
    path = str(item["path"])
    return {
        "repo": repo,
        "default_branch": branch,
        "repo_head_sha": repo_sha,
        "path": path,
        "ext": Path(path).suffix.lower(),
        "blob_sha": item.get("sha"),
        "bytes": item.get("size"),
        "download_url": f"https://raw.githubusercontent.com/{repo}/{repo_sha}/{path}",
        "html_url": f"https://github.com/{repo}/blob/{repo_sha}/{path}",
    }


def build_seed_file_manifest(
    *,
    pipeline_repo: Path,
    api_get: Any = _gh_api,
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seed_inputs = _load_seed_inputs(pipeline_repo)
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    per_repo: dict[str, dict[str, Any]] = {}
    totals = {"tla": 0, "cfg": 0, "tlaps": 0, "all": 0}

    for repo in seed_inputs["repos"]:
        repo_meta = api_get(f"/repos/{repo}")
        branch = str(repo_meta["default_branch"])
        branch_meta = api_get(f"/repos/{repo}/branches/{branch}")
        repo_sha = str(branch_meta["commit"]["sha"])
        tree = api_get(f"/repos/{repo}/git/trees/{repo_sha}?recursive=1")

        counts = {"tla": 0, "cfg": 0, "tlaps": 0, "all": 0}
        for item in tree.get("tree", []):
            if item.get("type") != "blob":
                continue
            path = str(item.get("path", ""))
            ext = Path(path).suffix.lower()
            if ext not in TRACKED_EXTENSIONS:
                continue
            rows.append(_file_record(repo, branch, repo_sha, item))
            counts[ext[1:]] += 1
            counts["all"] += 1

        per_repo[repo] = {
            "default_branch": branch,
            "repo_head_sha": repo_sha,
            "counts": counts,
        }
        for key in totals:
            totals[key] += counts[key]

    rows.sort(key=lambda row: (row["repo"].lower(), row["path"].lower()))
    summary = {
        "schema": "chattla_ai4fm_public_seed_file_manifest_v1",
        "generated_at": generated_at,
        "pipeline_repo": pipeline_repo.name,
        "seed_repo_inputs": len(seed_inputs["repos"]),
        "configured_org_inputs": len(seed_inputs["orgs"]),
        "configured_user_inputs": len(seed_inputs["users"]),
        "kept_rows": len(rows),
        "tracked_extensions": list(TRACKED_EXTENSIONS),
        "totals": totals,
        "per_repo": per_repo,
        "notes": [
            "This artifact materializes the committed public seed-repo lane from tla-dataset-pipeline.",
            "Counts reflect .tla, .cfg, and .tlaps files visible in the current GitHub default-branch trees.",
        ],
    }
    return rows, summary


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    out: Path,
    *,
    repo: Path = REPO,
) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    final_summary = dict(summary)
    final_summary["out"] = str(out.relative_to(repo))
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_summary["summary"] = str(summary_path.relative_to(repo))
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-repo", type=Path, default=DEFAULT_PIPELINE_REPO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_seed_file_manifest(pipeline_repo=args.pipeline_repo)
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
