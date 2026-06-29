import json

from scripts.build_ai4fm_public_seed_license_manifest import build_report


def test_build_report_joins_seed_counts_with_license_metadata() -> None:
    discovery_rows = [
        {
            "repo": "example/alpha",
            "license_spdx": "MIT",
            "html_url": "https://github.com/example/alpha",
            "query_hits": ["seed"],
        },
        {
            "repo": "example/beta",
            "license_spdx": None,
            "html_url": "https://github.com/example/beta",
            "query_hits": ["seed", "query:extension:tla"],
        },
        {
            "repo": "example/ignored",
            "license_spdx": "Apache-2.0",
            "html_url": "https://github.com/example/ignored",
            "query_hits": ["query:extension:tla"],
        },
    ]
    seed_summary = {
        "seed_repo_inputs": 3,
        "totals": {"all": 9, "tla": 6},
        "per_repo": {
            "example/alpha": {
                "default_branch": "main",
                "repo_head_sha": "a" * 40,
                "counts": {"all": 4, "tla": 3, "cfg": 1, "tlaps": 0},
            },
            "example/beta": {
                "default_branch": "master",
                "repo_head_sha": "b" * 40,
                "counts": {"all": 2, "tla": 2, "cfg": 0, "tlaps": 0},
            },
            "example/gamma": {
                "default_branch": "main",
                "repo_head_sha": "c" * 40,
                "counts": {"all": 3, "tla": 1, "cfg": 1, "tlaps": 1},
            },
        },
    }

    report = build_report(
        discovery_rows=discovery_rows,
        seed_summary=seed_summary,
        generated_at="2026-06-29T00:00:00+00:00",
    )

    assert report["seed_repo_inputs"] == 3
    assert report["tracked_seed_files"] == 9
    assert report["tracked_tla_files"] == 6
    assert report["license_summary"]["repo_counts"] == {"MIT": 1, "UNKNOWN": 2}
    assert report["license_summary"]["tracked_tla_file_counts"] == {"MIT": 3, "UNKNOWN": 3}
    assert report["license_summary"]["tracked_file_counts"] == {"MIT": 4, "UNKNOWN": 5}
    assert report["license_summary"]["clearly_permissive_repo_count"] == 1
    assert report["license_summary"]["caution_repo_count"] == 2
    assert report["caution_repos"] == ["example/beta", "example/gamma"]
    assert report["missing_discovery_records"] == ["example/gamma"]

    alpha = next(repo for repo in report["repos"] if repo["repo"] == "example/alpha")
    beta = next(repo for repo in report["repos"] if repo["repo"] == "example/beta")
    gamma = next(repo for repo in report["repos"] if repo["repo"] == "example/gamma")

    assert alpha["clearly_permissive_license"] is True
    assert beta["license_spdx"] == "UNKNOWN"
    assert beta["query_hits"] == ["seed", "query:extension:tla"]
    assert gamma["html_url"] == "https://github.com/example/gamma"
    assert gamma["clearly_permissive_license"] is False

    json.dumps(report)
