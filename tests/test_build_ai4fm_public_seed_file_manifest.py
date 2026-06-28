import json
from pathlib import Path

from scripts.build_ai4fm_public_seed_file_manifest import build_seed_file_manifest, write_outputs


def test_build_seed_file_manifest_counts_seed_repo_files(tmp_path: Path) -> None:
    pipeline_repo = tmp_path / "pipeline"
    (pipeline_repo / "config" / "seeds").mkdir(parents=True)
    (pipeline_repo / "config" / "seeds" / "repos.yaml").write_text(
        "\n".join(
            [
                "---",
                "repos:",
                "  - example/alpha",
                "  - example/beta",
                "orgs: []",
                "users: []",
                "",
            ]
        ),
        encoding="utf-8",
    )

    payloads = {
        "/repos/example/alpha": {"default_branch": "main"},
        "/repos/example/alpha/branches/main": {"commit": {"sha": "alpha123"}},
        "/repos/example/alpha/git/trees/alpha123?recursive=1": {
            "tree": [
                {"path": "SpecA.tla", "type": "blob", "sha": "a1", "size": 10},
                {"path": "SpecA.cfg", "type": "blob", "sha": "a2", "size": 5},
                {"path": "README.md", "type": "blob", "sha": "a3", "size": 1},
            ]
        },
        "/repos/example/beta": {"default_branch": "master"},
        "/repos/example/beta/branches/master": {"commit": {"sha": "beta456"}},
        "/repos/example/beta/git/trees/beta456?recursive=1": {
            "tree": [
                {"path": "dir/SpecB.tla", "type": "blob", "sha": "b1", "size": 20},
                {"path": "proof/SpecB.tlaps", "type": "blob", "sha": "b2", "size": 7},
                {"path": "dir/notes.txt", "type": "blob", "sha": "b3", "size": 2},
            ]
        },
    }

    rows, summary = build_seed_file_manifest(
        pipeline_repo=pipeline_repo,
        api_get=payloads.__getitem__,
        generated_at="2026-06-28T00:00:00+00:00",
    )

    assert len(rows) == 4
    assert rows[0]["repo"] == "example/alpha"
    assert rows[0]["ext"] == ".cfg"
    assert rows[1]["ext"] == ".tla"
    assert rows[-1]["ext"] == ".tlaps"
    assert rows[-1]["download_url"] == (
        "https://raw.githubusercontent.com/example/beta/beta456/proof/SpecB.tlaps"
    )
    assert summary["seed_repo_inputs"] == 2
    assert summary["kept_rows"] == 4
    assert summary["totals"]["tla"] == 2
    assert summary["totals"]["cfg"] == 1
    assert summary["totals"]["tlaps"] == 1
    assert summary["totals"]["all"] == 4
    assert summary["per_repo"]["example/alpha"]["counts"]["all"] == 2
    assert summary["per_repo"]["example/beta"]["counts"]["tlaps"] == 1


def test_write_outputs_uses_repo_relative_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    out = repo / "data" / "processed" / "seed_manifest.jsonl"
    rows = [{"repo": "example/alpha", "path": "SpecA.tla"}]
    summary = {"kept_rows": 1}

    final_summary = write_outputs(rows, summary, out, repo=repo)

    assert final_summary["out"] == "data/processed/seed_manifest.jsonl"
    assert final_summary["summary"] == "data/processed/seed_manifest.summary.json"
    loaded = json.loads((repo / final_summary["summary"]).read_text(encoding="utf-8"))
    assert loaded["out"] == "data/processed/seed_manifest.jsonl"
