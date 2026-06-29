import json
from pathlib import Path

from scripts.build_ai4fm_public_seed_tla_modules import build_seed_tla_modules, write_outputs


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_seed_tla_modules_fetches_tla_rows_and_skips_non_modules(tmp_path: Path) -> None:
    manifest = tmp_path / "seed_manifest.jsonl"
    _write_jsonl(
        manifest,
        [
            {
                "repo": "example/alpha",
                "path": "SpecA.tla",
                "ext": ".tla",
                "download_url": "https://example.com/SpecA.tla",
                "html_url": "https://example.com/blob/SpecA.tla",
                "repo_head_sha": "alpha123",
            },
            {
                "repo": "example/alpha",
                "path": "SpecA.cfg",
                "ext": ".cfg",
                "download_url": "https://example.com/SpecA.cfg",
                "html_url": "https://example.com/blob/SpecA.cfg",
                "repo_head_sha": "alpha123",
            },
            {
                "repo": "example/beta",
                "path": "notes/NotAModule.tla",
                "ext": ".tla",
                "download_url": "https://example.com/NotAModule.tla",
                "html_url": "https://example.com/blob/NotAModule.tla",
                "repo_head_sha": "beta456",
            },
        ],
    )

    fetched = {
        "https://example.com/SpecA.tla": "---- MODULE SpecA ----\nEXTENDS Naturals\n====\n",
        "https://example.com/NotAModule.tla": "\\* helper file without module header\n",
    }

    rows, summary = build_seed_tla_modules(
        manifest,
        fetch_text=fetched.__getitem__,
        generated_at="2026-06-29T00:00:00+00:00",
    )

    assert len(rows) == 1
    assert rows[0]["module"] == "SpecA"
    assert rows[0]["repo"] == "example/alpha"
    assert rows[0]["source_path"] == "SpecA.tla"
    assert rows[0]["content"].startswith("---- MODULE SpecA ----")
    assert rows[0]["content_sha256"]
    assert summary["manifest_rows"] == 3
    assert summary["tla_candidates"] == 2
    assert summary["kept_rows"] == 1
    assert summary["skipped_non_tla"] == 1
    assert summary["skipped_missing_module_header"] == 1
    assert summary["duplicate_modules"] == {}


def test_build_seed_tla_modules_tracks_duplicate_module_names(tmp_path: Path) -> None:
    manifest = tmp_path / "seed_manifest.jsonl"
    _write_jsonl(
        manifest,
        [
            {
                "repo": "example/alpha",
                "path": "a/SpecA.tla",
                "ext": ".tla",
                "download_url": "https://example.com/a/SpecA.tla",
                "html_url": "https://example.com/blob/a/SpecA.tla",
                "repo_head_sha": "alpha123",
            },
            {
                "repo": "example/beta",
                "path": "b/SpecA.tla",
                "ext": ".tla",
                "download_url": "https://example.com/b/SpecA.tla",
                "html_url": "https://example.com/blob/b/SpecA.tla",
                "repo_head_sha": "beta456",
            },
        ],
    )

    fetched = {
        "https://example.com/a/SpecA.tla": "---- MODULE SpecA ----\n====\n",
        "https://example.com/b/SpecA.tla": "---- MODULE SpecA ----\nEXTENDS Naturals\n====\n",
    }

    rows, summary = build_seed_tla_modules(
        manifest,
        fetch_text=fetched.__getitem__,
        generated_at="2026-06-29T00:00:00+00:00",
    )

    assert len(rows) == 2
    assert summary["duplicate_modules"] == {"SpecA": 2}


def test_write_outputs_handles_out_of_repo_target(tmp_path: Path) -> None:
    rows = [{"module": "SpecA", "repo": "example/alpha", "source_path": "SpecA.tla", "content": "---- MODULE SpecA ----\n====\n"}]
    summary = {"kept_rows": 1}
    out = tmp_path / "ai4fm_public_seed_tla_modules_v1.jsonl"

    final_summary = write_outputs(rows, summary, out)

    assert final_summary["out"] == str(out)
    assert final_summary["summary"] == str(out.with_suffix(".summary.json"))
