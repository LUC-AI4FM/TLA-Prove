#!/usr/bin/env python3
"""Build a public AI4FM repository discovery manifest from the live GitHub recipe."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised only if PyYAML is unavailable
    yaml = None

from scripts.inspect_ai4fm_public_dataset_surface import _git_head, _parse_dvc_lock

DEFAULT_PIPELINE_REPO = Path("/tmp/LUC-AI4FM-tla-dataset-pipeline")
DEFAULT_OUT = REPO / "data" / "processed" / "ai4fm_public_discovery_manifest_v1.jsonl"
DEFAULT_SUMMARY_OUT = REPO / "data" / "processed" / "ai4fm_public_discovery_manifest_v1.summary.json"

REPO_FIELDS = """
nameWithOwner
url
isArchived
isFork
stargazerCount
pushedAt
defaultBranchRef {
  name
  target {
    ... on Commit {
      oid
    }
  }
}
licenseInfo {
  spdxId
}
"""


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is not None:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _load_seed_inputs(pipeline_repo: Path) -> dict[str, list[str]]:
    payload = _load_yaml(pipeline_repo / "config" / "seeds" / "repos.yaml")
    return {
        "repos": [str(item) for item in payload.get("repos", []) if item],
        "orgs": [str(item) for item in payload.get("orgs", []) if item],
        "users": [str(item) for item in payload.get("users", []) if item],
    }


def _load_queries(pipeline_repo: Path) -> list[str]:
    payload = _load_yaml(pipeline_repo / "config" / "seeds" / "queries.yaml")
    return [str(item) for item in payload.get("queries", []) if item]


def _load_search_limit(pipeline_repo: Path) -> int:
    limits_path = pipeline_repo / "config" / "runtime" / "limits.yaml"
    payload = _load_yaml(limits_path) if limits_path.exists() else {}
    discovery = payload.get("discovery", {})
    if isinstance(discovery, dict):
        value = discovery.get("max_results_per_query")
        if isinstance(value, int) and value > 0:
            return value
    return 100


def _gh_api_graphql(*args: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["gh", "api", "graphql", *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def fetch_seed_repo_live(repo: str) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    payload = _gh_api_graphql(
        "-f",
        f"query=query {{ repository(owner:{json.dumps(owner)}, name:{json.dumps(name)}) {{ {REPO_FIELDS} }} }}",
    )
    node = payload.get("data", {}).get("repository")
    if not isinstance(node, dict):
        raise RuntimeError(f"Could not fetch GitHub metadata for seed repo {repo}")
    return node


def search_repositories_live(query: str, limit: int) -> dict[str, Any]:
    payload = _gh_api_graphql(
        "-f",
        f"query=query($q: String!, $n: Int!) {{ search(type: REPOSITORY, query: $q, first: $n) {{ repositoryCount nodes {{ ... on Repository {{ {REPO_FIELDS} }} }} }} }}",
        "-F",
        f"q={query}",
        "-F",
        f"n={limit}",
    )
    search = payload.get("data", {}).get("search", {})
    nodes = search.get("nodes", []) if isinstance(search, dict) else []
    repository_count = search.get("repositoryCount", len(nodes)) if isinstance(search, dict) else len(nodes)
    return {
        "repository_count": repository_count if isinstance(repository_count, int) else len(nodes),
        "nodes": [node for node in nodes if isinstance(node, dict)],
    }


def _normalize_record(node: dict[str, Any], *, source: str, discovered_at: str) -> dict[str, Any]:
    branch = node.get("defaultBranchRef") or {}
    target = branch.get("target") or {}
    record: dict[str, Any] = {
        "repo": node["nameWithOwner"],
        "html_url": node["url"],
        "default_branch": branch["name"],
        "sha": target["oid"],
        "license_spdx": (node.get("licenseInfo") or {}).get("spdxId"),
        "discovered_at": discovered_at,
        "query_hits": [source],
        "repo_meta": {
            "archived": bool(node.get("isArchived")),
            "fork": bool(node.get("isFork")),
            "stargazers_count": int(node.get("stargazerCount", 0)),
            "pushed_at": node.get("pushedAt"),
        },
    }
    return record


def _merge_records(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged["query_hits"] = sorted(set(existing.get("query_hits", []) + incoming.get("query_hits", [])))
    if "repo_meta" in existing or "repo_meta" in incoming:
        merged["repo_meta"] = dict(existing.get("repo_meta", {}))
        merged["repo_meta"].update(incoming.get("repo_meta", {}))
    return merged


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_public_discovery_manifest(
    *,
    pipeline_repo: Path,
    fetch_seed_repo: Callable[[str], dict[str, Any]],
    search_repositories: Callable[[str, int], dict[str, Any]],
    discovered_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seed_inputs = _load_seed_inputs(pipeline_repo)
    queries = _load_queries(pipeline_repo)
    search_limit = _load_search_limit(pipeline_repo)
    discovered_at = discovered_at or datetime.now(timezone.utc).isoformat()

    records_by_repo: dict[str, dict[str, Any]] = {}
    for repo in seed_inputs["repos"]:
        record = _normalize_record(fetch_seed_repo(repo), source="seed", discovered_at=discovered_at)
        records_by_repo[record["repo"]] = _merge_records(records_by_repo[record["repo"]], record) if record["repo"] in records_by_repo else record

    query_results_by_query: dict[str, dict[str, int]] = {}
    for query in queries:
        result = search_repositories(query, search_limit)
        nodes = result.get("nodes", [])
        query_results_by_query[query] = {
            "repository_count": int(result.get("repository_count", len(nodes))),
            "returned": len(nodes),
        }
        for node in nodes:
            record = _normalize_record(node, source=f"query:{query}", discovered_at=discovered_at)
            records_by_repo[record["repo"]] = _merge_records(records_by_repo[record["repo"]], record) if record["repo"] in records_by_repo else record

    dvc_lock = pipeline_repo / "dvc.lock"
    rows = sorted(records_by_repo.values(), key=lambda row: row["repo"].lower())
    zero_result_queries = [query for query, stats in query_results_by_query.items() if stats["returned"] == 0]
    summary = {
        "generated_at": discovered_at,
        "pipeline_repo": pipeline_repo.name,
        "pipeline_git_head": _git_head(pipeline_repo),
        "source_schema": "data_contracts/schemas/source_record.schema.json",
        "seed_repo_inputs": len(seed_inputs["repos"]),
        "configured_org_inputs": len(seed_inputs["orgs"]),
        "configured_user_inputs": len(seed_inputs["users"]),
        "operational_seed_mode": "repos_only",
        "search_queries": len(queries),
        "search_limit": search_limit,
        "query_results_by_query": query_results_by_query,
        "zero_result_queries": zero_result_queries,
        "unique_repo_records": len(rows),
        "dvc_surface": _parse_dvc_lock(dvc_lock) if dvc_lock.exists() else {},
        "notes": [
            "This manifest reflects the pipeline's public seed repo list plus live repository search queries.",
            "Configured org/user seed lists are preserved for auditability, but the pipeline's checked-in loader currently ignores them.",
            "The larger DVC-backed raw and parsed corpora are not reproduced here; this artifact captures the public discovery layer only.",
        ],
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-repo", type=Path, default=DEFAULT_PIPELINE_REPO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_OUT)
    args = parser.parse_args()

    rows, summary = build_public_discovery_manifest(
        pipeline_repo=args.pipeline_repo,
        fetch_seed_repo=fetch_seed_repo_live,
        search_repositories=search_repositories_live,
    )
    _write_jsonl(args.out, rows)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "summary_out": str(args.summary_out),
                "rows": len(rows),
                "zero_result_queries": summary["zero_result_queries"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
