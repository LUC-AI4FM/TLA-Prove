import sys
import types
from pathlib import Path

from src.training.publish_hf import (
    _patch_readme,
    fetch_remote_paths_via_http,
    fetch_remote_repo_paths,
    main,
    max_published_version,
    next_version_for_publish,
    publish,
    publish_readiness_blockers,
)


class _Sibling:
    def __init__(self, rfilename: str) -> None:
        self.rfilename = rfilename


class _ModelInfo:
    def __init__(self, siblings: list[_Sibling]) -> None:
        self.siblings = siblings


class _ApiWithListFiles:
    def list_repo_files(self, *, repo_id: str, repo_type: str) -> list[str]:
        assert repo_id == "EricSpencer00/chattla-20b"
        assert repo_type == "model"
        return [
            ".gitattributes",
            "gguf/chattla-20b-v19-Q8_0.gguf",
            "gguf/chattla-20b-v21-Q8_0.gguf",
        ]


class _ApiWithModelInfo:
    def model_info(self, repo_id: str) -> _ModelInfo:
        assert repo_id == "EricSpencer00/chattla-20b"
        return _ModelInfo(
            [
                _Sibling(".gitattributes"),
                _Sibling("gguf/chattla-20b-v20-Q8_0.gguf"),
            ]
        )


def test_max_published_version_reads_highest_gguf_version() -> None:
    assert (
        max_published_version(
            [
                ".gitattributes",
                "gguf/chattla-20b-v18-Q8_0.gguf",
                "gguf/chattla-20b-v21-Q8_0.gguf",
                "README.md",
            ]
        )
        == 21
    )


def test_next_version_for_publish_uses_remote_when_local_state_lags() -> None:
    new_version, remote_last = next_version_for_publish(
        local_last=15,
        remote_paths=[
            "gguf/chattla-20b-v20-Q8_0.gguf",
            "gguf/chattla-20b-v21-Q8_0.gguf",
        ],
    )

    assert remote_last == 21
    assert new_version == 22


def test_next_version_for_publish_respects_override() -> None:
    new_version, remote_last = next_version_for_publish(
        local_last=15,
        remote_paths=["gguf/chattla-20b-v21-Q8_0.gguf"],
        version_override=99,
    )

    assert remote_last == 21
    assert new_version == 99


def test_fetch_remote_repo_paths_prefers_list_repo_files() -> None:
    paths = fetch_remote_repo_paths(_ApiWithListFiles(), "EricSpencer00/chattla-20b")

    assert "gguf/chattla-20b-v21-Q8_0.gguf" in paths


def test_fetch_remote_repo_paths_falls_back_to_model_info() -> None:
    paths = fetch_remote_repo_paths(_ApiWithModelInfo(), "EricSpencer00/chattla-20b")

    assert paths == [".gitattributes", "gguf/chattla-20b-v20-Q8_0.gguf"]


def test_fetch_remote_paths_via_http_reads_siblings(monkeypatch) -> None:
    payload = {
        "siblings": [
            {"rfilename": "gguf/chattla-20b-v20-Q8_0.gguf"},
            {"rfilename": "gguf/chattla-20b-v21-Q8_0.gguf"},
            {"rfilename": "README.md"},
        ]
    }

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout=30: _Resp())
    monkeypatch.setattr("json.load", lambda _resp: payload)

    paths = fetch_remote_paths_via_http("EricSpencer00/chattla-20b")

    assert paths == [
        "gguf/chattla-20b-v20-Q8_0.gguf",
        "gguf/chattla-20b-v21-Q8_0.gguf",
        "README.md",
    ]


def test_patch_readme_updates_stale_template_version_references() -> None:
    text = """
# ChatTLA-20b (v15)

## Benchmark Results (v15, 3-shot self-correct)

huggingface-cli download EricSpencer00/chattla-20b \\
    gguf/chattla-20b-v15-Q8_0.gguf \\
    --local-dir ./chattla

./llama-cli -m chattla/gguf/chattla-20b-v15-Q8_0.gguf \\
    -n 1024 --temp 0.4

├── chattla-20b-v15-Q8_0.gguf   # Quantised GGUF for Ollama / llama.cpp
""".strip()

    patched = _patch_readme(text, version=22, stats=None)

    assert "# ChatTLA-20b (v22)" in patched
    assert "## Benchmark Results (v22, 3-shot self-correct)" in patched
    assert "gguf/chattla-20b-v22-Q8_0.gguf" in patched
    assert "chattla/gguf/chattla-20b-v22-Q8_0.gguf" in patched
    assert "chattla-20b-v22-Q8_0.gguf   # Quantised GGUF for Ollama / llama.cpp" in patched
    assert "v15" not in patched


def test_patch_readme_repairs_stale_gguf_filename_when_title_is_current() -> None:
    text = """
# ChatTLA-20b (v21)

└── gguf/
    ├── chattla-20b-v15-Q8_0.gguf   # Quantised GGUF for Ollama / llama.cpp
""".strip()

    patched = _patch_readme(text, version=21, stats=None)

    assert "chattla-20b-v21-Q8_0.gguf   # Quantised GGUF for Ollama / llama.cpp" in patched
    assert "v15" not in patched


def test_publish_readiness_blockers_reject_zero_pass_full_benchmark() -> None:
    blockers = publish_readiness_blockers(
        gguf_present=True,
        readme_present=True,
        stats={
            "source_csv": "benchmark_results_fc128best_full_20260628_235102.csv",
            "mtime": 1000.0,
            "n": 20,
            "sany": 0,
            "tlc": 0,
            "avg_struct": 0.85,
        },
        benchmark_max_age_hours=24.0,
        now=1000.0,
    )

    assert blockers == [
        "latest full benchmark has zero SANY and zero TLC passes; do not publish this model"
    ]


def test_publish_aborts_before_upload_when_readiness_is_blocked(tmp_path: Path, monkeypatch) -> None:
    gguf_dir = tmp_path / "gguf"
    gguf_dir.mkdir()
    (gguf_dir / "chattla-20b-Q8_0.gguf").write_text("gguf", encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text("# card\n", encoding="utf-8")

    class _FakeHfApi:
        upload_calls = 0

        def __init__(self, token=None) -> None:
            self.token = token

        def list_repo_files(self, *, repo_id: str, repo_type: str) -> list[str]:
            return []

        def upload_file(self, **_kwargs) -> None:
            type(self).upload_calls += 1

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(HfApi=_FakeHfApi))
    monkeypatch.setattr(
        "src.training.publish_hf.latest_full_benchmark_stats",
        lambda: {
            "source_csv": "benchmark_results_fc128best_full_20260628_235102.csv",
            "source_path": str(tmp_path / "benchmark_results_fc128best_full_20260628_235102.csv"),
            "mtime": 1000.0,
            "n": 20,
            "sany": 0,
            "tlc": 0,
            "avg_struct": 0.85,
        },
    )
    monkeypatch.setattr("src.training.publish_hf.time.time", lambda: 1000.0)
    monkeypatch.setenv("HF_TOKEN", "test-token")

    result = publish(
        repo_id="EricSpencer00/chattla-20b",
        dry_run=False,
        gguf_dir=gguf_dir,
        merged_model_dir=tmp_path / "merged_model",
        require_fresh_full_benchmark_hours=24.0,
    )

    assert result is None
    assert _FakeHfApi.upload_calls == 0


def test_publish_dry_run_does_not_require_huggingface_hub(tmp_path: Path, monkeypatch) -> None:
    gguf_dir = tmp_path / "gguf"
    gguf_dir.mkdir()
    (gguf_dir / "chattla-20b-Q8_0.gguf").write_text("gguf", encoding="utf-8")

    monkeypatch.setattr("src.training.publish_hf._load_hf_api_class", lambda required: None)
    monkeypatch.setattr(
        "src.training.publish_hf.latest_full_benchmark_stats",
        lambda: {
            "source_csv": "benchmark_results_good_full.csv",
            "source_path": str(tmp_path / "benchmark_results_good_full.csv"),
            "mtime": 1000.0,
            "n": 20,
            "sany": 10,
            "tlc": 8,
            "avg_struct": 0.91,
        },
    )
    monkeypatch.setattr("src.training.publish_hf.time.time", lambda: 1000.0)
    monkeypatch.setattr(
        "src.training.publish_hf._load_state",
        lambda: {"last_published_version": 15},
    )
    monkeypatch.setattr(
        "src.training.publish_hf.fetch_remote_paths_via_http",
        lambda repo_id: [
            "gguf/chattla-20b-v20-Q8_0.gguf",
            "gguf/chattla-20b-v21-Q8_0.gguf",
        ],
    )

    result = publish(
        repo_id="EricSpencer00/chattla-20b",
        dry_run=True,
        gguf_dir=gguf_dir,
        merged_model_dir=tmp_path / "merged_model",
        require_fresh_full_benchmark_hours=24.0,
    )

    assert result == 22


def test_publish_dry_run_uses_http_fallback_for_remote_version(tmp_path: Path, monkeypatch) -> None:
    gguf_dir = tmp_path / "gguf"
    gguf_dir.mkdir()
    (gguf_dir / "chattla-20b-Q8_0.gguf").write_text("gguf", encoding="utf-8")
    monkeypatch.setattr("src.training.publish_hf._load_hf_api_class", lambda required: None)
    monkeypatch.setattr(
        "src.training.publish_hf.fetch_remote_paths_via_http",
        lambda repo_id: [
            "gguf/chattla-20b-v20-Q8_0.gguf",
            "gguf/chattla-20b-v21-Q8_0.gguf",
        ],
    )
    monkeypatch.setattr(
        "src.training.publish_hf.latest_full_benchmark_stats",
        lambda: {
            "source_csv": "benchmark_results_good_full.csv",
            "source_path": str(tmp_path / "benchmark_results_good_full.csv"),
            "mtime": 1000.0,
            "n": 20,
            "sany": 10,
            "tlc": 8,
            "avg_struct": 0.91,
        },
    )
    monkeypatch.setattr("src.training.publish_hf.time.time", lambda: 1000.0)
    monkeypatch.setattr(
        "src.training.publish_hf._load_state",
        lambda: {"last_published_version": 15},
    )

    result = publish(
        repo_id="EricSpencer00/chattla-20b",
        dry_run=True,
        gguf_dir=gguf_dir,
        merged_model_dir=tmp_path / "merged_model",
        require_fresh_full_benchmark_hours=24.0,
    )

    assert result == 22


def test_publish_aborts_when_remote_version_state_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    gguf_dir = tmp_path / "gguf"
    gguf_dir.mkdir()
    (gguf_dir / "chattla-20b-Q8_0.gguf").write_text("gguf", encoding="utf-8")

    class _BrokenHfApi:
        upload_calls = 0

        def __init__(self, token=None) -> None:
            self.token = token

        def list_repo_files(self, *, repo_id: str, repo_type: str) -> list[str]:
            raise RuntimeError("network down")

        def upload_file(self, **_kwargs) -> None:
            type(self).upload_calls += 1

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(HfApi=_BrokenHfApi))
    monkeypatch.setattr("src.training.publish_hf.fetch_remote_paths_via_http", lambda repo_id: None)
    monkeypatch.setattr(
        "src.training.publish_hf.latest_full_benchmark_stats",
        lambda: {
            "source_csv": "benchmark_results_good_full.csv",
            "source_path": str(tmp_path / "benchmark_results_good_full.csv"),
            "mtime": 1000.0,
            "n": 20,
            "sany": 10,
            "tlc": 8,
            "avg_struct": 0.91,
        },
    )
    monkeypatch.setattr("src.training.publish_hf.time.time", lambda: 1000.0)
    monkeypatch.setenv("HF_TOKEN", "test-token")

    result = publish(
        repo_id="EricSpencer00/chattla-20b",
        dry_run=False,
        gguf_dir=gguf_dir,
        merged_model_dir=tmp_path / "merged_model",
        require_fresh_full_benchmark_hours=24.0,
    )

    assert result is None
    assert _BrokenHfApi.upload_calls == 0


def test_publish_dry_run_returns_none_when_readiness_is_blocked(tmp_path: Path, monkeypatch) -> None:
    gguf_dir = tmp_path / "gguf"
    gguf_dir.mkdir()
    (gguf_dir / "chattla-20b-Q8_0.gguf").write_text("gguf", encoding="utf-8")

    monkeypatch.setattr("src.training.publish_hf._load_hf_api_class", lambda required: None)
    monkeypatch.setattr(
        "src.training.publish_hf.latest_full_benchmark_stats",
        lambda: {
            "source_csv": "benchmark_results_fc128best_full_20260628_235102.csv",
            "source_path": str(tmp_path / "benchmark_results_fc128best_full_20260628_235102.csv"),
            "mtime": 1000.0,
            "n": 20,
            "sany": 0,
            "tlc": 0,
            "avg_struct": 0.85,
        },
    )
    monkeypatch.setattr("src.training.publish_hf.time.time", lambda: 1000.0)

    result = publish(
        repo_id="EricSpencer00/chattla-20b",
        dry_run=True,
        gguf_dir=gguf_dir,
        merged_model_dir=tmp_path / "merged_model",
        require_fresh_full_benchmark_hours=24.0,
    )

    assert result is None


def test_main_returns_nonzero_for_blocked_dry_run(monkeypatch) -> None:
    monkeypatch.setattr("src.training.publish_hf.publish", lambda **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["publish_hf.py", "--dry-run"])

    assert main() == 1
