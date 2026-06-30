import json
from pathlib import Path

from scripts.inspect_hf_publish_readiness import (
    DEFAULT_OUT,
    build_failure_surface,
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
    benchmark_csv = tmp_path / "benchmark_results_fc128best_full_20260628_235102.csv"
    _write(
        benchmark_csv,
        "\n".join(
            [
                "model,benchmark_id,name,domain,difficulty,sany_pass,tlc_pass,structural_score,tlc_tier,runtime_s,generated_spec,init_present,next_present,init_level_ok,next_level_ok,invariants_declared,tlc_depth1_ok,partial_credit,expected_invariant_overlap,plan_used",
                'chattla:20b-fc128best,BM001,Mutual Exclusion,scheduling,2,0,0,0.8,bronze,30.0,"---- MODULE A ----\nVARIABLES x, x\nNext == ...\n====",0,0,0,0,0,0,0.0,0,0',
            ]
        )
        + "\n",
    )

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
            "source_path": str(benchmark_csv),
            "mtime": 0,
            "execution": {
                "self_correct": False,
                "use_plan": False,
                "attempts": 1,
                "inference_mode": "single-shot",
            },
        },
        now_fn=lambda: 3600,
    )

    assert report["ready_to_publish"] is False
    assert (
        "latest full benchmark has zero SANY and zero TLC passes; do not publish this model"
        in report["blockers"]
    )
    assert report["claim_status"]["supports_public_benchmark_100_percent_claim"] is False
    assert "0/20 SANY and 0/20 TLC" in report["claim_status"]["reason"]
    assert report["failure_surface"]["rows"] == 1
    assert report["failure_surface"]["aggregate"]["rows_with_all_core_components"] == 0
    assert report["benchmark"]["execution"]["inference_mode"] == "single-shot"


def test_build_failure_surface_summarizes_missing_components_and_red_flags(tmp_path: Path) -> None:
    csv_path = tmp_path / "benchmark_results_fc128best_full.csv"
    _write(
        csv_path,
        "\n".join(
            [
                "model,benchmark_id,name,domain,difficulty,sany_pass,tlc_pass,structural_score,tlc_tier,runtime_s,generated_spec,init_present,next_present,init_level_ok,next_level_ok,invariants_declared,tlc_depth1_ok,partial_credit,expected_invariant_overlap,plan_used",
                'chattla:20b-fc128best,BM001,Mutual Exclusion,scheduling,2,0,0,0.8,bronze,30.0,"---- MODULE A ----\nVARIABLES x, x\nInit == TRUE\nNext == ...\n(* placeholder *)\n====",0,0,0,0,0,0,0.0,0,0',
                'chattla:20b-fc128best,BM002,Queue,storage,2,0,0,0.9,bronze,31.0,"---- MODULE B ----\nVARIABLES q\nInit == TRUE\nNext == \\E x : x #= 1\n====",1,0,1,0,0,0,0.1,0,1',
                'chattla:20b-fc128best,BM003,Commit,transaction,3,0,0,0.7,bronze,32.0,"---- MODULE C ----\nCONSTDEF Foo == 1\n====",0,0,0,0,0,0,0.0,0,0',
            ]
        )
        + "\n",
    )

    surface = build_failure_surface(csv_path, benchmark_model="chattla:20b-fc128best")

    assert surface["rows"] == 3
    assert surface["aggregate"]["rows_with_any_core_component"] == 1
    assert surface["aggregate"]["rows_with_all_core_components"] == 0
    assert surface["aggregate"]["rows_with_no_core_components"] == 2
    assert surface["core_component_failures"]["missing_init_present_rows"] == 2
    assert surface["core_component_failures"]["missing_next_present_rows"] == 3
    assert surface["red_flags"]["obvious_placeholder_rows"] == 1
    assert surface["red_flags"]["duplicate_variables_rows"] == 1
    assert surface["red_flags"]["pseudo_tla_token_rows"] == 2
    assert surface["planning"]["plan_used_rows"] == 1
    assert surface["sample_benchmark_ids"]["no_core_components"] == ["BM001", "BM003"]


def test_build_report_surfaces_supported_public_benchmark_claim(tmp_path: Path) -> None:
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
        fetch_remote_paths=lambda _repo: ["gguf/chattla-20b-v21-Q8_0.gguf"],
        benchmark_stats={
            "n": 20,
            "sany": 20,
            "tlc": 20,
            "avg_struct": 1.0,
            "source_csv": "benchmark_results_full.csv",
            "source_path": str(tmp_path / "benchmark_results_full.csv"),
            "mtime": 0,
            "model": "chattla:20b",
        },
        now_fn=lambda: 3600,
    )

    assert report["claim_status"]["supports_public_benchmark_100_percent_claim"] is True
    assert "20/20 SANY and 20/20 TLC" in report["claim_status"]["reason"]


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
