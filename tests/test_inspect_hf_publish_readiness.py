import json
from pathlib import Path

from scripts.inspect_hf_publish_readiness import (
    DEFAULT_OUT,
    build_report,
    default_out_path_for_benchmark_model,
    sync_state_to_remote,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_report_detects_remote_state_drift_and_local_blockers(tmp_path: Path) -> None:
    state_path = tmp_path / "hf_publish_state.json"
    _write(
        state_path,
        json.dumps(
            {
                "last_published_version": 15,
                "note": "Next RL/automated publish will upload as v12.",
                "last_repo": "EricSpencer00/chattla-20b",
            }
        ),
    )
    gguf_dir = tmp_path / "outputs" / "gguf"
    merged_model_dir = tmp_path / "outputs" / "merged_model"
    readme = tmp_path / "outputs" / "hf_readme" / "README.md"
    _write(readme, "# README\n")

    report = build_report(
        repo_id="EricSpencer00/chattla-20b",
        gguf_dir=gguf_dir,
        gguf_search_dirs=(gguf_dir,),
        merged_model_dir=merged_model_dir,
        state_path=state_path,
        readme_template=readme,
        benchmark_max_age_hours=24,
        fetch_remote_paths=lambda _repo: [
            "gguf/chattla-20b-v20-Q8_0.gguf",
            "gguf/chattla-20b-v21-Q8_0.gguf",
        ],
        benchmark_stats=None,
        now_fn=lambda: 0,
    )

    assert report["ready_to_publish"] is False
    assert "local GGUF artifact missing under outputs/gguf" in report["blockers"]
    assert "no full benchmark CSV found" in report["blockers"]
    assert report["remote"]["latest_published_version"] == 21
    assert report["next_publish_version"] == 22
    assert "local publish state v15 lags remote GGUF state v21" in report["warnings"]
    assert "hf_publish_state note is stale relative to last_published_version" in report["warnings"]


def test_default_out_path_keeps_canonical_lane_stable_and_candidates_separate() -> None:
    assert default_out_path_for_benchmark_model("chattla:20b") == DEFAULT_OUT
    assert default_out_path_for_benchmark_model("chattla:20b-fc128best") == (
        DEFAULT_OUT.parent / "hf_publish_readiness.chattla_20b_fc128best.json"
    )


def test_build_report_accepts_local_gguf_from_fallback_dir(tmp_path: Path) -> None:
    state_path = tmp_path / "hf_publish_state.json"
    _write(
        state_path,
        json.dumps(
            {
                "last_published_version": 21,
                "last_repo": "EricSpencer00/chattla-20b",
                "note": "aligned",
            }
        ),
    )
    gguf_dir = tmp_path / "outputs" / "gguf"
    fallback_dir = tmp_path / "outputs" / "gguf_fc128_best"
    _write(fallback_dir / "chattla-20b-Q8_0.gguf", "placeholder gguf")
    readme = tmp_path / "outputs" / "hf_readme" / "README.md"
    _write(readme, "# README\n")

    report = build_report(
        repo_id="EricSpencer00/chattla-20b",
        gguf_dir=gguf_dir,
        gguf_search_dirs=(gguf_dir, fallback_dir),
        state_path=state_path,
        readme_template=readme,
        benchmark_max_age_hours=24,
        fetch_remote_paths=lambda _repo: [
            "gguf/chattla-20b-v21-Q8_0.gguf",
        ],
        benchmark_stats=None,
        now_fn=lambda: 0,
    )

    assert "local GGUF artifact missing under outputs/gguf" not in report["blockers"]
    assert report["local"]["latest_gguf"] == str(fallback_dir / "chattla-20b-Q8_0.gguf")
    assert str(fallback_dir / "chattla-20b-Q8_0.gguf") in report["local"]["gguf_files"]


def test_build_report_blocks_degenerate_zero_pass_full_benchmark(tmp_path: Path) -> None:
    state_path = tmp_path / "hf_publish_state.json"
    _write(
        state_path,
        json.dumps(
            {
                "last_published_version": 21,
                "last_repo": "EricSpencer00/chattla-20b",
                "note": "aligned",
            }
        ),
    )
    gguf_dir = tmp_path / "outputs" / "gguf"
    _write(gguf_dir / "chattla-20b-Q8_0.gguf", "placeholder gguf")
    readme = tmp_path / "outputs" / "hf_readme" / "README.md"
    _write(readme, "# README\n")

    report = build_report(
        repo_id="EricSpencer00/chattla-20b",
        gguf_dir=gguf_dir,
        gguf_search_dirs=(gguf_dir,),
        state_path=state_path,
        readme_template=readme,
        benchmark_max_age_hours=24,
        fetch_remote_paths=lambda _repo: [
            "gguf/chattla-20b-v21-Q8_0.gguf",
        ],
        benchmark_stats={
            "n": 20,
            "sany": 0,
            "tlc": 0,
            "avg_struct": 0.8557,
            "source_csv": "benchmark_results_fc128best_full_20260628_235102.csv",
            "source_path": str(tmp_path / "benchmark_results_fc128best_full_20260628_235102.csv"),
            "mtime": 0,
        },
        now_fn=lambda: 3600,
    )

    assert report["ready_to_publish"] is False
    assert (
        "latest full benchmark has zero SANY and zero TLC passes; do not publish this model"
        in report["blockers"]
    )


def test_build_report_requests_specific_benchmark_model(tmp_path: Path, monkeypatch) -> None:
    state_path = tmp_path / "hf_publish_state.json"
    _write(
        state_path,
        json.dumps(
            {
                "last_published_version": 21,
                "last_repo": "EricSpencer00/chattla-20b",
                "note": "aligned",
            }
        ),
    )
    gguf_dir = tmp_path / "outputs" / "gguf"
    _write(gguf_dir / "chattla-20b-Q8_0.gguf", "placeholder gguf")
    readme = tmp_path / "outputs" / "hf_readme" / "README.md"
    _write(readme, "# README\n")

    seen: list[str | None] = []

    monkeypatch.setattr(
        "scripts.inspect_hf_publish_readiness.latest_full_benchmark_stats",
        lambda benchmark_model=None: seen.append(benchmark_model) or {
            "n": 20,
            "sany": 6,
            "tlc": 3,
            "avg_struct": 0.9,
            "source_csv": "benchmark_results_rl_c128_full_20260324_190446.csv",
            "source_path": str(tmp_path / "benchmark_results_rl_c128_full_20260324_190446.csv"),
            "mtime": 0,
            "model": benchmark_model,
        },
    )

    report = build_report(
        repo_id="EricSpencer00/chattla-20b",
        gguf_dir=gguf_dir,
        gguf_search_dirs=(gguf_dir,),
        state_path=state_path,
        readme_template=readme,
        benchmark_max_age_hours=0,
        fetch_remote_paths=lambda _repo: ["gguf/chattla-20b-v21-Q8_0.gguf"],
        benchmark_model="chattla:20b",
    )

    assert seen == ["chattla:20b"]
    assert report["benchmark"]["model"] == "chattla:20b"


def test_sync_state_to_remote_updates_local_counter(tmp_path: Path) -> None:
    state_path = tmp_path / "hf_publish_state.json"
    _write(
        state_path,
        json.dumps(
            {
                "last_published_version": 15,
                "last_repo": "EricSpencer00/chattla-20b",
                "note": "stale",
            }
        ),
    )
    report = {
        "repo_id": "EricSpencer00/chattla-20b",
        "remote": {
            "latest_published_version": 21,
            "gguf_files": [
                "gguf/chattla-20b-v21-Q8_0.gguf",
            ],
        },
    }

    changed = sync_state_to_remote(state_path=state_path, report=report)

    assert changed is True
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["last_published_version"] == 21
    assert saved["last_gguf_path_in_repo"] == "gguf/chattla-20b-v21-Q8_0.gguf"
    assert saved["last_repo"] == "EricSpencer00/chattla-20b"
    assert "aligned to remote Hugging Face publish surface" in saved["note"]
