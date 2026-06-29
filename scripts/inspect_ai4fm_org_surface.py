#!/usr/bin/env python3
"""Inspect the public GitHub org surface behind the broader AI4FM corpus story."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ORG = "LUC-AI4FM"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "ai4fm_org_surface.json"
EXPECTED_CORE_REPOS: list[tuple[str, str]] = [
    ("FormaLLM", "benchmark"),
    ("TLA-Prove", "public-corpora"),
    ("tla-dataset-pipeline", "pipeline"),
]


def _fetch_org_repos(org: str) -> list[dict[str, Any]]:
    request = Request(
        f"https://api.github.com/orgs/{org}/repos?per_page=100",
        headers={"User-Agent": "ChatTLA/inspect_ai4fm_org_surface"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError(f"Expected GitHub repo list for org {org}, got: {type(payload).__name__}")
    return [item for item in payload if isinstance(item, dict)]


def _repo_role(name: str) -> str:
    for expected_name, role in EXPECTED_CORE_REPOS:
        if name == expected_name:
            return role
    return "adjacent"


def _normalize_repo(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    return {
        "name": name,
        "full_name": payload.get("full_name"),
        "html_url": payload.get("html_url"),
        "default_branch": payload.get("default_branch"),
        "pushed_at": payload.get("pushed_at"),
        "size": payload.get("size"),
        "role": _repo_role(name),
    }


def build_report(*, org: str, repo_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    repos = sorted((_normalize_repo(payload) for payload in repo_payloads), key=lambda item: str(item["name"]).lower())
    repo_names = {str(repo["name"]) for repo in repos}
    corpus_relevant = [name for name, _role in EXPECTED_CORE_REPOS if name in repo_names]
    missing = [name for name, _role in EXPECTED_CORE_REPOS if name not in repo_names]
    warnings = []
    if missing:
        warnings.append(f"Missing expected public AI4FM core repos: {', '.join(missing)}.")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "org": org,
        "public_repo_count": len(repos),
        "summary": {
            "corpus_relevant_repo_count": len(corpus_relevant),
            "corpus_relevant_repos": corpus_relevant,
            "adjacent_repo_count": len(repos) - len(corpus_relevant),
        },
        "repos": repos,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", default=DEFAULT_ORG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--repos-json",
        type=Path,
        help="Optional local JSON file containing a GitHub-style repo list for offline/reproducible runs.",
    )
    args = parser.parse_args()

    if args.repos_json is not None:
        repo_payloads = json.loads(args.repos_json.read_text(encoding="utf-8"))
        if not isinstance(repo_payloads, list):
            raise SystemExit("--repos-json must point to a JSON list of repository payloads")
    else:
        repo_payloads = _fetch_org_repos(args.org)

    report = build_report(org=args.org, repo_payloads=repo_payloads)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
