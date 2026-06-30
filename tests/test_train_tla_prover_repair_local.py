import os
import json
import subprocess
from pathlib import Path

from scripts.train_rl_repair import DEFAULT_SMOKE_MODEL
from scripts.train_tla_prover_repair_local import build_run_plan, compact_plan, run_refresh_pipeline

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "train_tla_prover_repair_local.py"


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_run_plan_defaults_to_merged_repair_corpus_and_preflight(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.jsonl",
        '{"repair_id":"R1","before_score":0.2}\n{"repair_id":"R2","before_score":0.4}\n',
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        (
            '{"rows": 510, "health": {"ok": true, "warnings": []}, '
            '"kept_rows_by_source": {"synthetic": 491, "benchmark": 19}, '
            '"missing_sources": ["data/processed/ralph_repair_pairs.jsonl"]}\n'
        ),
    )
    monkeypatch.setattr(
        "scripts.train_tla_prover_repair_local._resolve_preflight_report",
        lambda **_kwargs: {
            "ok": True,
            "runtime_dependencies": {"ok": True, "available": ["torch"], "missing": []},
            "merged_summary": {"rows": 510},
        },
    )

    plan = build_run_plan(
        repo=tmp_path,
        trajectory_files=None,
        include_benchmark_repair_pairs=False,
        output_dir=None,
        extra_args=[],
        preflight_only=True,
        refresh_corpus=False,
        python_executable="/tmp/test-python",
    )

    assert plan["resolved_trajectory_files"] == ["data/processed/tla_prover_repair_train_v1.jsonl"]
    assert plan["using_merged_default"] is True
    assert plan["output_dir"].endswith("outputs/checkpoints_rl_repair")
    assert plan["preflight_report"]["ok"] is True
    assert plan["preflight_report"]["merged_summary"]["rows"] == 510
    assert plan["preflight_report"]["requested_python_executable"] == "/tmp/test-python"
    assert plan["preflight_report"]["runtime_dependencies"]["requested_python_executable"] == "/tmp/test-python"
    assert plan["python_executable"] == "/tmp/test-python"
    assert plan["bootstrap_recommendation"] is None
    assert plan["refresh_corpus"] is False
    assert plan["refresh_steps"] == []
    assert plan["refresh_command"] is None
    assert plan["command"] == [
        "/tmp/test-python",
        "-m",
        "scripts.train_rl_repair",
        "--trajectory-file",
        "data/processed/tla_prover_repair_train_v1.jsonl",
        "--output-dir",
        str(tmp_path / "outputs/checkpoints_rl_repair"),
        "--preflight-only",
    ]


def test_build_run_plan_uses_custom_sources_and_separate_output_dir(tmp_path: Path, monkeypatch) -> None:
    _write(tmp_path / "custom/repair_pairs.jsonl", '{"repair_id":"C1","before_score":0.3}\n')
    _write(
        tmp_path / "data/processed/benchmark_repair_pairs_fc128best.jsonl",
        '{"repair_id":"B1","before_score":0.1}\n',
    )
    monkeypatch.setattr(
        "scripts.train_tla_prover_repair_local._resolve_preflight_report",
        lambda **_kwargs: {
            "ok": True,
            "runtime_dependencies": {"ok": True, "available": ["torch"], "missing": []},
            "merged_summary": None,
        },
    )

    plan = build_run_plan(
        repo=tmp_path,
        trajectory_files=["custom/repair_pairs.jsonl"],
        include_benchmark_repair_pairs=True,
        output_dir=None,
        extra_args=["--difficulty", "hard"],
        preflight_only=False,
        refresh_corpus=False,
        python_executable="/tmp/test-python",
    )

    assert plan["resolved_trajectory_files"] == [
        "custom/repair_pairs.jsonl",
        "data/processed/benchmark_repair_pairs_fc128best.jsonl",
    ]
    assert plan["using_merged_default"] is False
    assert plan["output_dir"].endswith("outputs/checkpoints_rl_repair_custom-repair-pairs-jsonl")
    assert plan["command"] == [
        "/tmp/test-python",
        "-m",
        "scripts.train_rl_repair",
        "--trajectory-file",
        "custom/repair_pairs.jsonl",
        "--trajectory-file",
        "data/processed/benchmark_repair_pairs_fc128best.jsonl",
        "--output-dir",
        str(tmp_path / "outputs/checkpoints_rl_repair_custom-repair-pairs-jsonl"),
        "--difficulty",
        "hard",
    ]


def test_cli_preflight_dry_run_executes_without_import_error() -> None:
    completed = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--preflight",
            "--dry-run",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "CHATTLA_RUNTIME_IMPORT_TIMEOUT_S": "2",
        },
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["schema"] == "chattla_tla_prover_local_repair_plan_v1"
    assert payload["preflight_only"] is True
    assert "runtime_dependencies" in payload["preflight_report"]


def test_build_run_plan_preflight_report_tracks_smoke_runtime(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.jsonl",
        '{"repair_id":"R1","before_score":0.2}\n',
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        '{"rows": 1, "health": {"ok": true, "warnings": []}, "kept_rows_by_source": {"benchmark": 1}}\n',
    )
    monkeypatch.setattr(
        "scripts.train_tla_prover_repair_local._resolve_preflight_report",
        lambda **_kwargs: {
            "ok": False,
            "model": DEFAULT_SMOKE_MODEL,
            "runtime": {
                "implicit_smoke_model": True,
                "device_map": "cpu",
                "dtype": "float32",
            },
            "runtime_dependencies": {"ok": False, "available": [], "missing": []},
        },
    )

    plan = build_run_plan(
        repo=tmp_path,
        trajectory_files=None,
        include_benchmark_repair_pairs=False,
        output_dir=None,
        extra_args=["--smoke"],
        preflight_only=True,
        refresh_corpus=False,
        python_executable="/tmp/test-python",
    )

    assert plan["command"][-1] == "--smoke"
    assert plan["preflight_report"]["model"] == DEFAULT_SMOKE_MODEL
    assert plan["preflight_report"]["runtime"]["implicit_smoke_model"] is True
    assert plan["preflight_report"]["runtime"]["device_map"] == "cpu"


def test_build_run_plan_resolves_preflight_report_via_selected_python(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.jsonl",
        '{"repair_id":"R1","before_score":0.2}\n',
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        '{"rows": 1, "health": {"ok": true, "warnings": []}, "kept_rows_by_source": {"benchmark": 1}}\n',
    )
    captured: dict[str, object] = {}

    def fake_resolve_preflight_report(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "runtime_dependencies": {"ok": True, "available": [], "missing": []}}

    monkeypatch.setattr(
        "scripts.train_tla_prover_repair_local._resolve_preflight_report",
        fake_resolve_preflight_report,
    )

    plan = build_run_plan(
        repo=tmp_path,
        trajectory_files=None,
        include_benchmark_repair_pairs=False,
        output_dir=None,
        extra_args=["--smoke"],
        preflight_only=True,
        refresh_corpus=False,
        python_executable="/tmp/test-python",
    )

    assert plan["preflight_report"]["ok"] is True
    assert captured["python_executable"] == "/tmp/test-python"
    assert captured["extra_args"] == ["--smoke"]
    assert plan["preflight_report"]["requested_python_executable"] == "/tmp/test-python"
    assert plan["preflight_report"]["runtime_dependencies"]["requested_python_executable"] == "/tmp/test-python"


def test_build_run_plan_prefers_repo_venv_python_when_env_unset(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.jsonl",
        '{"repair_id":"R1","before_score":0.2}\n',
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        '{"rows": 1, "health": {"ok": true, "warnings": []}, "kept_rows_by_source": {"benchmark": 1}}\n',
    )
    _write(tmp_path / ".venv/bin/python")
    monkeypatch.delenv("CHATTLA_PYTHON", raising=False)
    monkeypatch.delenv("PYTHON", raising=False)
    monkeypatch.setattr("scripts.train_tla_prover_repair_local.REPO", tmp_path)
    monkeypatch.setattr(
        "scripts.train_tla_prover_repair_local._resolve_preflight_report",
        lambda **kwargs: {
            "ok": True,
            "runtime_dependencies": {"ok": True, "available": [], "missing": []},
            "selected_python": kwargs["python_executable"],
        },
    )

    plan = build_run_plan(
        repo=tmp_path,
        trajectory_files=None,
        include_benchmark_repair_pairs=False,
        output_dir=None,
        extra_args=[],
        preflight_only=True,
        refresh_corpus=False,
    )

    assert plan["python_executable"] == str(tmp_path / ".venv/bin/python")
    assert plan["preflight_report"]["selected_python"] == str(tmp_path / ".venv/bin/python")
    assert plan["preflight_report"]["requested_python_executable"] == str(tmp_path / ".venv/bin/python")
    assert (
        plan["preflight_report"]["runtime_dependencies"]["requested_python_executable"]
        == str(tmp_path / ".venv/bin/python")
    )


def test_build_run_plan_surfaces_bootstrap_recommendation_for_missing_repo_venv_deps(
    tmp_path: Path, monkeypatch
) -> None:
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.jsonl",
        '{"repair_id":"R1","before_score":0.2}\n',
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        '{"rows": 1, "health": {"ok": true, "warnings": []}, "kept_rows_by_source": {"benchmark": 1}}\n',
    )
    _write(tmp_path / ".venv/bin/python")
    monkeypatch.delenv("CHATTLA_PYTHON", raising=False)
    monkeypatch.delenv("PYTHON", raising=False)
    monkeypatch.setattr("scripts.train_tla_prover_repair_local.REPO", tmp_path)
    monkeypatch.setattr(
        "scripts.train_tla_prover_repair_local._resolve_preflight_report",
        lambda **_kwargs: {
            "ok": False,
            "runtime_dependencies": {"ok": False, "available": [], "missing": [{"module": "torch"}]},
        },
    )

    plan = build_run_plan(
        repo=tmp_path,
        trajectory_files=None,
        include_benchmark_repair_pairs=False,
        output_dir=None,
        extra_args=[],
        preflight_only=True,
        refresh_corpus=False,
    )

    assert plan["bootstrap_recommendation"]["reason"] == "selected_python_missing_training_dependencies"
    assert (
        plan["bootstrap_recommendation"]["command"]
        == "CHATTLA_BOOTSTRAP_REQUIREMENTS_FILE=requirements-repair-bootstrap.txt bash scripts/launch_rl.sh setup"
    )
    assert "repo .venv is missing required repair-training dependencies" in plan["bootstrap_recommendation"]["message"]


def test_build_run_plan_surfaces_refresh_pipeline(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.jsonl",
        '{"repair_id":"R1","before_score":0.2}\n',
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        '{"rows": 1, "health": {"ok": true, "warnings": []}, "kept_rows_by_source": {"benchmark": 1}}\n',
    )
    monkeypatch.setattr(
        "scripts.train_tla_prover_repair_local._resolve_preflight_report",
        lambda **_kwargs: {
            "ok": True,
            "runtime_dependencies": {"ok": True, "available": [], "missing": []},
        },
    )

    plan = build_run_plan(
        repo=tmp_path,
        trajectory_files=None,
        include_benchmark_repair_pairs=False,
        output_dir=None,
        extra_args=[],
        preflight_only=True,
        refresh_corpus=True,
        python_executable="/tmp/test-python",
    )

    assert plan["refresh_corpus"] is True
    assert plan["refresh_steps"][0] == ["python3", "scripts/build_tla_prover_full_dataset_repair_queue.py"]
    assert "--allowed-tier silver" in plan["refresh_command"]


def test_run_refresh_pipeline_executes_steps_in_order(tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def fake_runner(cmd: list[str], *, cwd: Path, check: bool):
        seen.append(list(cmd))
        assert cwd == tmp_path
        assert check is True
        return None

    run_refresh_pipeline(repo=tmp_path, runner=fake_runner)

    assert seen == [
        ["python3", "scripts/build_tla_prover_full_dataset_repair_queue.py"],
        ["python3", "scripts/build_tla_prover_full_dataset_repair_evidence.py"],
        [
            "python3",
            "scripts/build_tla_prover_full_dataset_validated_repair_pairs.py",
            "--allowed-tier",
            "gold",
            "--allowed-tier",
            "silver",
        ],
        ["python3", "scripts/build_tla_prover_repair_corpus.py"],
    ]


def test_compact_plan_surfaces_runtime_readiness_and_missing_modules(tmp_path: Path, monkeypatch) -> None:
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.jsonl",
        '{"repair_id":"R1","before_score":0.2}\n',
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        '{"rows": 1, "health": {"ok": true, "warnings": []}, "kept_rows_by_source": {"benchmark": 1}}\n',
    )
    monkeypatch.setattr(
        "scripts.train_tla_prover_repair_local._resolve_preflight_report",
        lambda **_kwargs: {
            "ok": False,
            "runtime_dependencies": {
                "ok": False,
                "available": ["torch", "yaml"],
                "missing": [
                    {"module": "datasets.Dataset", "error": "TimeoutExpired: import timed out after 2.0s"},
                    {"module": "peft.LoraConfig", "error": "TimeoutExpired: import timed out after 2.0s"},
                ],
            },
        },
    )

    plan = build_run_plan(
        repo=tmp_path,
        trajectory_files=None,
        include_benchmark_repair_pairs=False,
        output_dir=None,
        extra_args=[],
        preflight_only=True,
        refresh_corpus=False,
        python_executable=str(tmp_path / ".venv/bin/python"),
    )

    compact = compact_plan(plan)

    assert compact["preflight_ok"] is False
    assert compact["local_runtime_ready"] is False
    assert compact["runtime_missing_modules"] == ["datasets.Dataset", "peft.LoraConfig"]
    assert compact["bootstrap_recommendation"]["command"] == (
        "CHATTLA_BOOTSTRAP_REQUIREMENTS_FILE=requirements-repair-bootstrap.txt bash scripts/launch_rl.sh setup"
    )


def test_cli_can_write_and_compact_plan_json(tmp_path: Path) -> None:
    out = tmp_path / "repair-plan.json"
    completed = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--preflight",
            "--dry-run",
            "--out",
            str(out),
            "--compact",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "CHATTLA_RUNTIME_IMPORT_TIMEOUT_S": "2",
        },
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["schema"] == "chattla_tla_prover_local_repair_plan_compact_v1"
    assert "local_runtime_ready" in payload
    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted["schema"] == "chattla_tla_prover_local_repair_plan_v1"
