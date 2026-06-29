from src.training.publish_hf import (
    _patch_readme,
    fetch_remote_repo_paths,
    max_published_version,
    next_version_for_publish,
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
