from src.training.publish_hf import (
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
