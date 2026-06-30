import subprocess

from scripts.train_rl_repair import (
    DEFAULT_SMOKE_MODEL,
    DEFAULT_BENCHMARK_REPAIR_PAIRS,
    DEFAULT_MERGED_REPAIR_PAIRS,
    DEFAULT_MERGED_REPAIR_SUMMARY,
    DEFAULT_REPAIR_PAIRS,
    build_preflight_report,
    build_arg_parser,
    build_runtime_config,
    _probe_runtime_dependencies,
    resolve_trajectory_files,
)


def test_resolve_trajectory_files_defaults_to_merged_repair_corpus_when_present(monkeypatch) -> None:
    parser = build_arg_parser()
    args = parser.parse_args([])
    monkeypatch.setattr("scripts.train_rl_repair._path_exists", lambda path: path == DEFAULT_MERGED_REPAIR_PAIRS)
    assert resolve_trajectory_files(args) == [DEFAULT_MERGED_REPAIR_PAIRS]


def test_resolve_trajectory_files_falls_back_to_available_component_sources(monkeypatch) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--include-benchmark-repair-pairs"])
    monkeypatch.setattr(
        "scripts.train_rl_repair._path_exists",
        lambda path: path in {DEFAULT_BENCHMARK_REPAIR_PAIRS},
    )
    assert resolve_trajectory_files(args) == [DEFAULT_BENCHMARK_REPAIR_PAIRS]


def test_resolve_trajectory_files_appends_benchmark_pairs() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(
        [
            "--trajectory-file",
            "custom_a.jsonl",
            "--trajectory-file",
            "custom_b.jsonl",
            "--include-benchmark-repair-pairs",
        ]
    )
    assert resolve_trajectory_files(args) == [
        "custom_a.jsonl",
        "custom_b.jsonl",
        DEFAULT_BENCHMARK_REPAIR_PAIRS,
    ]


def test_build_preflight_report_uses_merged_summary_for_default_corpus(tmp_path, monkeypatch) -> None:
    parser = build_arg_parser()
    args = parser.parse_args([])
    monkeypatch.setattr(
        "scripts.train_rl_repair._probe_runtime_dependencies",
        lambda: {
            "ok": True,
            "available": ["torch", "yaml", "datasets", "peft", "transformers", "trl"],
            "missing": [],
        },
    )

    merged_path = tmp_path / DEFAULT_MERGED_REPAIR_PAIRS
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path.write_text(
        "\n".join(
            [
                '{"repair_id":"R1","before_score":0.1}',
                '{"repair_id":"R2","before_score":0.2}',
                '{"repair_id":"R1","before_score":0.3}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / DEFAULT_MERGED_REPAIR_SUMMARY
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        (
            '{"rows": 510, "health": {"ok": true, "warnings": []}, '
            '"kept_rows_by_source": {"synthetic": 491, "benchmark": 19}, '
            '"missing_sources": ["data/processed/ralph_repair_pairs.jsonl"]}'
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_preflight_report(args, repo_root=tmp_path)

    assert report["ok"] is True
    assert report["trajectory_files"] == [DEFAULT_MERGED_REPAIR_PAIRS]
    assert report["raw_rows"] == 3
    assert report["unique_repair_ids"] == 2
    assert report["using_merged_default"] is True
    assert report["runtime_dependencies"]["ok"] is True
    assert report["merged_summary"]["rows"] == 510
    assert report["merged_summary"]["health"]["ok"] is True
    assert report["merged_summary"]["kept_rows_by_source"] == {"synthetic": 491, "benchmark": 19}
    assert report["merged_summary"]["missing_sources"] == ["data/processed/ralph_repair_pairs.jsonl"]


def test_build_preflight_report_flags_missing_selected_corpus(tmp_path, monkeypatch) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--trajectory-file", "missing.jsonl"])
    monkeypatch.setattr(
        "scripts.train_rl_repair._probe_runtime_dependencies",
        lambda: {
            "ok": True,
            "available": ["torch", "yaml", "datasets", "peft", "transformers", "trl"],
            "missing": [],
        },
    )

    report = build_preflight_report(args, repo_root=tmp_path)

    assert report["ok"] is False
    assert report["missing_files"] == ["missing.jsonl"]
    assert report["raw_rows"] == 0
    assert report["unique_repair_ids"] == 0


def test_build_runtime_config_uses_tiny_cpu_defaults_for_implicit_smoke_model(monkeypatch) -> None:
    parser = build_arg_parser()
    monkeypatch.setattr("scripts.train_rl_repair._resolve_base_model", lambda: "base-model")
    args = parser.parse_args(["--smoke"])

    runtime = build_runtime_config(args)

    assert runtime["model"] == DEFAULT_SMOKE_MODEL
    assert runtime["device_map"] == "cpu"
    assert runtime["dtype"] == "float32"
    assert runtime["trainer_bf16"] is False
    assert runtime["max_completion_length"] == 128
    assert runtime["max_prompt_tokens"] == 512


def test_build_runtime_config_preserves_explicit_runtime_choices_for_smoke(monkeypatch) -> None:
    parser = build_arg_parser()
    monkeypatch.setattr("scripts.train_rl_repair._resolve_base_model", lambda: "base-model")
    args = parser.parse_args(
        [
            "--smoke",
            "--model",
            "custom-model",
            "--device-map",
            "auto",
            "--dtype",
            "bfloat16",
            "--max-completion-length",
            "96",
            "--max-prompt-tokens",
            "400",
        ]
    )

    runtime = build_runtime_config(args)

    assert runtime["model"] == "custom-model"
    assert runtime["device_map"] == "auto"
    assert runtime["dtype"] == "bfloat16"
    assert runtime["trainer_bf16"] is True
    assert runtime["max_completion_length"] == 96
    assert runtime["max_prompt_tokens"] == 400


def test_probe_runtime_dependencies_reports_timeout(monkeypatch) -> None:
    class _Completed:
        def __init__(self, returncode: int = 0, stderr: str = "", stdout: str = "") -> None:
            self.returncode = returncode
            self.stderr = stderr
            self.stdout = stdout

    def fake_run(cmd, **kwargs):
        if "torch" in cmd[-1]:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=3.0)
        return _Completed()

    monkeypatch.setattr("scripts.train_rl_repair.subprocess.run", fake_run)

    report = _probe_runtime_dependencies(module_names=("yaml", "torch"), python_executable="/tmp/python", timeout_s=3.0)

    assert report["python_executable"] == "/tmp/python"
    assert report["timeout_s"] == 3.0
    assert report["available"] == ["yaml"]
    assert report["missing"] == [
        {"module": "torch", "error": "TimeoutExpired: import timed out after 3.0s"}
    ]
    assert report["ok"] is False


def test_build_preflight_report_marks_missing_runtime_dependencies(tmp_path, monkeypatch) -> None:
    parser = build_arg_parser()
    args = parser.parse_args([])

    merged_path = tmp_path / DEFAULT_MERGED_REPAIR_PAIRS
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path.write_text('{"repair_id":"R1","before_score":0.2}\n', encoding="utf-8")

    summary_path = tmp_path / DEFAULT_MERGED_REPAIR_SUMMARY
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        '{"rows": 1, "health": {"ok": true, "warnings": []}, "kept_rows_by_source": {"benchmark": 1}}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "scripts.train_rl_repair._probe_runtime_dependencies",
        lambda: {
            "ok": False,
            "available": ["yaml"],
            "missing": [
                {"module": "torch", "error": "ModuleNotFoundError: No module named 'torch'"},
            ],
        },
    )

    report = build_preflight_report(args, repo_root=tmp_path)

    assert report["ok"] is False
    assert report["runtime_dependencies"]["ok"] is False
    assert report["runtime_dependencies"]["missing"] == [
        {"module": "torch", "error": "ModuleNotFoundError: No module named 'torch'"},
    ]
