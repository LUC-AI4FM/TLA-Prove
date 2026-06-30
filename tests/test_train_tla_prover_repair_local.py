import json
import subprocess
from pathlib import Path

from scripts.train_rl_repair import DEFAULT_SMOKE_MODEL
from scripts.train_tla_prover_repair_local import build_run_plan

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
        python_executable="/tmp/test-python",
    )

    assert plan["resolved_trajectory_files"] == ["data/processed/tla_prover_repair_train_v1.jsonl"]
    assert plan["using_merged_default"] is True
    assert plan["output_dir"].endswith("outputs/checkpoints_rl_repair")
    assert plan["preflight_report"]["ok"] is True
    assert plan["preflight_report"]["merged_summary"]["rows"] == 510
    assert plan["python_executable"] == "/tmp/test-python"
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
        python_executable="/tmp/test-python",
    )

    assert plan["preflight_report"]["ok"] is True
    assert captured["python_executable"] == "/tmp/test-python"
    assert captured["extra_args"] == ["--smoke"]
