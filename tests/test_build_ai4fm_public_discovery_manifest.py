import json
from pathlib import Path

from scripts.build_ai4fm_public_discovery_manifest import build_public_discovery_manifest


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_public_discovery_manifest_merges_seed_and_query_hits(tmp_path: Path) -> None:
    pipeline = tmp_path / "tla-dataset-pipeline"
    _write(
        pipeline / "config" / "seeds" / "repos.yaml",
        "\n".join(
            [
                "---",
                "orgs:",
                "  - tlaplus",
                "repos:",
                "  - tlaplus/tlaplus",
                "  - Azure/azure-cosmos-tla",
                "users:",
                "  - muratdem",
                "",
            ]
        ),
    )
    _write(
        pipeline / "config" / "seeds" / "queries.yaml",
        "\n".join(
            [
                "---",
                "queries:",
                "  - extension:tla",
                "  - TLAPS extension:tla",
                "",
            ]
        ),
    )
    _write(
        pipeline / "config" / "runtime" / "limits.yaml",
        "\n".join(
            [
                "discovery:",
                "  max_results_per_query: 100",
                "",
            ]
        ),
    )
    _write(
        pipeline / "data_contracts" / "schemas" / "source_record.schema.json",
        json.dumps({"title": "SourceRecord"}),
    )
    _write(
        pipeline / "dvc.lock",
        "\n".join(
            [
                "schema: '2.0'",
                "stages:",
                "  pull:",
                "    outs:",
                "    - path: data/raw",
                "      size: 12034995",
                "      nfiles: 2628",
                "  parse:",
                "    deps:",
                "    - path: data/raw",
                "      size: 618486",
                "      nfiles: 227",
                "    outs:",
                "    - path: data/parsed",
                "      size: 22773073",
                "      nfiles: 3979",
                "",
            ]
        ),
    )

    seed_nodes = {
        "tlaplus/tlaplus": {
            "nameWithOwner": "tlaplus/tlaplus",
            "url": "https://github.com/tlaplus/tlaplus",
            "isArchived": False,
            "isFork": False,
            "stargazerCount": 10,
            "pushedAt": "2026-06-20T00:00:00Z",
            "defaultBranchRef": {"name": "master", "target": {"oid": "a" * 40}},
            "licenseInfo": {"spdxId": "MIT"},
        },
        "Azure/azure-cosmos-tla": {
            "nameWithOwner": "Azure/azure-cosmos-tla",
            "url": "https://github.com/Azure/azure-cosmos-tla",
            "isArchived": False,
            "isFork": False,
            "stargazerCount": 4,
            "pushedAt": "2026-06-18T00:00:00Z",
            "defaultBranchRef": {"name": "main", "target": {"oid": "b" * 40}},
            "licenseInfo": {"spdxId": "MIT"},
        },
    }

    def fetch_seed_repo(repo: str) -> dict:
        return seed_nodes[repo]

    def search_repositories(query: str, limit: int) -> dict:
        assert limit == 100
        if query == "extension:tla":
            return {
                "repository_count": 2,
                "nodes": [
                    {
                        "nameWithOwner": "tlaplus/tlaplus",
                        "url": "https://github.com/tlaplus/tlaplus",
                        "isArchived": False,
                        "isFork": False,
                        "stargazerCount": 10,
                        "pushedAt": "2026-06-20T00:00:00Z",
                        "defaultBranchRef": {"name": "master", "target": {"oid": "a" * 40}},
                        "licenseInfo": {"spdxId": "MIT"},
                    },
                    {
                        "nameWithOwner": "example/specs",
                        "url": "https://github.com/example/specs",
                        "isArchived": False,
                        "isFork": True,
                        "stargazerCount": 2,
                        "pushedAt": "2026-05-01T00:00:00Z",
                        "defaultBranchRef": {"name": "main", "target": {"oid": "c" * 40}},
                        "licenseInfo": {"spdxId": None},
                    },
                ],
            }
        return {"repository_count": 0, "nodes": []}

    records, summary = build_public_discovery_manifest(
        pipeline_repo=pipeline,
        fetch_seed_repo=fetch_seed_repo,
        search_repositories=search_repositories,
        discovered_at="2026-06-28T12:00:00+00:00",
    )

    assert [record["repo"] for record in records] == [
        "Azure/azure-cosmos-tla",
        "example/specs",
        "tlaplus/tlaplus",
    ]
    assert summary["seed_repo_inputs"] == 2
    assert summary["configured_org_inputs"] == 1
    assert summary["configured_user_inputs"] == 1
    assert summary["operational_seed_mode"] == "repos_only"
    assert summary["unique_repo_records"] == 3
    assert summary["search_queries"] == 2
    assert summary["query_results_by_query"]["extension:tla"]["returned"] == 2
    assert summary["query_results_by_query"]["TLAPS extension:tla"]["returned"] == 0
    assert summary["zero_result_queries"] == ["TLAPS extension:tla"]
    assert summary["dvc_surface"]["pull"]["nfiles"] == 2628

    tlaplus = next(record for record in records if record["repo"] == "tlaplus/tlaplus")
    assert tlaplus["query_hits"] == ["query:extension:tla", "seed"]
    assert tlaplus["repo_meta"]["stargazers_count"] == 10
    assert tlaplus["default_branch"] == "master"
    assert tlaplus["sha"] == "a" * 40
