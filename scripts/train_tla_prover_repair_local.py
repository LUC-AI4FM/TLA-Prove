#!/usr/bin/env python3
"""Launch local TLA prover repair training with reproducible corpus selection."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.train_rl_repair import (
    DEFAULT_BENCHMARK_REPAIR_PAIRS,
    DEFAULT_MERGED_REPAIR_PAIRS,
    build_arg_parser as build_train_rl_repair_arg_parser,
    build_preflight_report,
    build_runtime_config,
    resolve_trajectory_files,
)
from scripts.build_tla_prover_repair_corpus import DEFAULT_PROFILE, VALID_PROFILES, default_out_for_profile

BOOTSTRAP_ENV_COMMAND = "CHATTLA_BOOTSTRAP_REQUIREMENTS_FILE=requirements-repair-bootstrap.txt bash scripts/launch_rl.sh setup"
DEFAULT_PLAN_OUT = REPO / "outputs" / "manifests" / "tla_prover_local_repair_plan.json"
DEFAULT_LOCAL_RUNTIME_IMPORT_TIMEOUT_S = 10.0
REPAIR_REFRESH_STEPS: tuple[tuple[str, ...], ...] = (
    ("python3", "scripts/build_tla_prover_full_dataset_repair_queue.py"),
    ("python3", "scripts/build_tla_prover_full_dataset_repair_evidence.py"),
    (
        "python3",
        "scripts/build_tla_prover_full_dataset_validated_repair_pairs.py",
        "--allowed-tier",
        "gold",
        "--allowed-tier",
        "silver",
    ),
    (
        "python3",
        "scripts/build_tla_prover_full_dataset_validated_repair_pairs.py",
        "--allowed-tier",
        "gold",
        "--allowed-tier",
        "silver",
        "--include-harness",
        "--only-bucket",
        "skip_harness_repair",
        "--out",
        "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.jsonl",
    ),
    ("python3", "scripts/build_tla_prover_repair_corpus.py"),
)


def _resolve_python_executable() -> str:
    venv_python = REPO / ".venv" / "bin" / "python"
    for candidate in (
        os.environ.get("CHATTLA_PYTHON"),
        os.environ.get("PYTHON"),
        str(venv_python) if venv_python.exists() else None,
        sys.executable,
    ):
        if candidate:
            return candidate
    return "python3"


def _resolve_runtime_import_timeout_s(runtime_import_timeout_s: float | None = None) -> float:
    if runtime_import_timeout_s is not None:
        return float(runtime_import_timeout_s)
    env_value = os.environ.get("CHATTLA_RUNTIME_IMPORT_TIMEOUT_S")
    if env_value:
        return float(env_value)
    return DEFAULT_LOCAL_RUNTIME_IMPORT_TIMEOUT_S


def _all_missing_runtime_errors_are_timeouts(missing: list[dict[str, Any]]) -> bool:
    if not missing:
        return False
    return all("TimeoutExpired:" in str(entry.get("error") or "") for entry in missing)


def _bootstrap_recommendation(
    *,
    repo: Path,
    python_executable: str,
    preflight_report: dict[str, Any],
) -> dict[str, Any] | None:
    runtime_dependencies = dict(preflight_report.get("runtime_dependencies") or {})
    missing = list(runtime_dependencies.get("missing") or [])
    if not missing:
        return None
    if _all_missing_runtime_errors_are_timeouts(missing):
        return {
            "reason": "selected_python_runtime_import_timeouts",
            "selected_python": python_executable,
            "command": None,
            "message": (
                "Selected Python timed out while importing required repair-training modules. "
                "This looks like a native import/runtime blocker; bootstrap alone may not resolve native import/runtime blockers."
            ),
        }
    try:
        selected = Path(python_executable).resolve()
    except FileNotFoundError:
        selected = Path(python_executable)
    repo_venv = (repo / ".venv" / "bin" / "python").resolve()
    using_repo_venv = selected == repo_venv
    if using_repo_venv:
        return {
            "reason": "selected_python_missing_training_dependencies",
            "selected_python": str(selected),
            "command": BOOTSTRAP_ENV_COMMAND,
            "message": (
                "Selected repo .venv is missing required repair-training dependencies. "
                "Bootstrap the repo environment, then rerun this preflight."
            ),
        }
    return {
        "reason": "selected_python_missing_training_dependencies",
        "selected_python": str(selected),
        "command": BOOTSTRAP_ENV_COMMAND,
        "message": (
            "Selected Python is missing required repair-training dependencies. "
            "Bootstrap the repo .venv or set CHATTLA_PYTHON/PYTHON to a ready environment, then rerun this preflight."
        ),
    }


def _annotate_preflight_report_with_requested_python(
    report: dict[str, Any],
    *,
    python_executable: str,
) -> dict[str, Any]:
    annotated = dict(report)
    try:
        resolved_python = str(Path(python_executable).resolve())
    except FileNotFoundError:
        resolved_python = python_executable
    annotated["requested_python_executable"] = python_executable
    annotated["requested_python_executable_resolved"] = resolved_python
    runtime_dependencies = dict(annotated.get("runtime_dependencies") or {})
    if runtime_dependencies:
        runtime_dependencies.setdefault("requested_python_executable", python_executable)
        runtime_dependencies.setdefault("requested_python_executable_resolved", resolved_python)
        annotated["runtime_dependencies"] = runtime_dependencies
    return annotated


def _safe_label(value: str | None) -> str:
    if not value:
        return "custom"
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-").lower() or "custom"


def _profile_default_trajectory_file(repo: Path, repair_corpus_profile: str) -> str:
    return str(default_out_for_profile(repair_corpus_profile, repo=repo).relative_to(repo))


def _default_output_dir(repo: Path, resolved_trajectory_files: list[str], repair_corpus_profile: str) -> Path:
    if resolved_trajectory_files == [DEFAULT_MERGED_REPAIR_PAIRS]:
        return repo / "outputs" / "checkpoints_rl_repair"
    if repair_corpus_profile != DEFAULT_PROFILE and resolved_trajectory_files == [
        _profile_default_trajectory_file(repo, repair_corpus_profile)
    ]:
        return repo / "outputs" / f"checkpoints_rl_repair_{_safe_label(repair_corpus_profile)}"

    primary = next(
        (
            path
            for path in resolved_trajectory_files
            if path != DEFAULT_BENCHMARK_REPAIR_PAIRS
        ),
        resolved_trajectory_files[0] if resolved_trajectory_files else None,
    )
    return repo / "outputs" / f"checkpoints_rl_repair_{_safe_label(primary)}"


def _preflight_trajectory_files(
    *,
    repo: Path,
    trajectory_files: list[str] | None,
    include_benchmark_repair_pairs: bool,
    resolved_trajectory_files: list[str],
    repair_corpus_profile: str,
    refresh_corpus: bool,
) -> list[str]:
    if trajectory_files:
        return list(resolved_trajectory_files)
    if repair_corpus_profile == DEFAULT_PROFILE or not refresh_corpus:
        return list(resolved_trajectory_files)
    if all((repo / path).is_file() for path in resolved_trajectory_files):
        return list(resolved_trajectory_files)

    fallback_args = _build_args(
        trajectory_files=None,
        include_benchmark_repair_pairs=include_benchmark_repair_pairs,
    )
    return resolve_trajectory_files(fallback_args, repo_root=repo)


def _refresh_steps(repair_corpus_profile: str = DEFAULT_PROFILE) -> list[list[str]]:
    steps = [list(step) for step in REPAIR_REFRESH_STEPS[:-1]]
    final_step = list(REPAIR_REFRESH_STEPS[-1])
    if repair_corpus_profile != DEFAULT_PROFILE:
        final_step.extend(["--profile", repair_corpus_profile])
    steps.append(final_step)
    return steps


def _refresh_command(repair_corpus_profile: str = DEFAULT_PROFILE) -> str:
    return " && ".join(shlex.join(step) for step in _refresh_steps(repair_corpus_profile))


def run_refresh_pipeline(*, repo: Path, repair_corpus_profile: str = DEFAULT_PROFILE, runner=subprocess.run) -> None:
    for step in _refresh_steps(repair_corpus_profile):
        runner(step, cwd=repo, check=True)


def _build_args(
    *,
    trajectory_files: list[str] | None,
    include_benchmark_repair_pairs: bool,
) -> Namespace:
    return Namespace(
        trajectory_file=list(trajectory_files or []),
        include_benchmark_repair_pairs=include_benchmark_repair_pairs,
    )


def _build_train_rl_repair_args(
    *,
    trajectory_files: list[str] | None,
    include_benchmark_repair_pairs: bool,
    output_dir: str | None,
    extra_args: list[str],
) -> Namespace:
    parser = build_train_rl_repair_arg_parser()
    parsed = parser.parse_args(extra_args)
    parsed.trajectory_file = list(trajectory_files or [])
    parsed.include_benchmark_repair_pairs = include_benchmark_repair_pairs
    if output_dir is not None:
        parsed.output_dir = output_dir
    return parsed


def _resolve_preflight_report(
    *,
    repo: Path,
    python_executable: str,
    trajectory_files: list[str] | None,
    include_benchmark_repair_pairs: bool,
    extra_args: list[str],
    runtime_import_timeout_s: float,
) -> dict[str, Any]:
    preflight_args = _build_train_rl_repair_args(
        trajectory_files=trajectory_files,
        include_benchmark_repair_pairs=include_benchmark_repair_pairs,
        output_dir=None,
        extra_args=extra_args,
    )
    runtime = build_runtime_config(preflight_args)
    if Path(python_executable).resolve() == Path(sys.executable).resolve():
        report = build_preflight_report(
            preflight_args,
            repo_root=repo,
            runtime_import_timeout_s=runtime_import_timeout_s,
        )
        report["model"] = runtime["model"]
        report["runtime"] = runtime
        return report

    command = [python_executable, "-m", "scripts.train_rl_repair", "--preflight-only"]
    for path in list(trajectory_files or []):
        command.extend(["--trajectory-file", path])
    if include_benchmark_repair_pairs:
        command.append("--include-benchmark-repair-pairs")
    command.extend(extra_args)

    completed = subprocess.run(
        command,
        cwd=repo,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "CHATTLA_RUNTIME_IMPORT_TIMEOUT_S": str(runtime_import_timeout_s),
        },
    )
    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError(
            f"target preflight produced no JSON output (rc={completed.returncode}): "
            f"{completed.stderr.strip() or 'no stderr'}"
        )
    report = json.loads(stdout)
    if not isinstance(report, dict):
        raise RuntimeError("target preflight did not return a JSON object")
    return report


def build_run_plan(
    *,
    repo: Path,
    trajectory_files: list[str] | None,
    include_benchmark_repair_pairs: bool,
    repair_corpus_profile: str = DEFAULT_PROFILE,
    output_dir: str | None,
    extra_args: list[str],
    preflight_only: bool,
    refresh_corpus: bool,
    python_executable: str | None = None,
    runtime_import_timeout_s: float | None = None,
) -> dict[str, Any]:
    if repair_corpus_profile not in VALID_PROFILES:
        raise ValueError(f"repair_corpus_profile must be one of {VALID_PROFILES}, got {repair_corpus_profile!r}")
    args = _build_args(
        trajectory_files=trajectory_files,
        include_benchmark_repair_pairs=include_benchmark_repair_pairs,
    )
    if trajectory_files:
        resolved_trajectory_files = resolve_trajectory_files(args, repo_root=repo)
    else:
        resolved_trajectory_files = [_profile_default_trajectory_file(repo, repair_corpus_profile)]
    preflight_trajectory_files = _preflight_trajectory_files(
        repo=repo,
        trajectory_files=trajectory_files,
        include_benchmark_repair_pairs=include_benchmark_repair_pairs,
        resolved_trajectory_files=resolved_trajectory_files,
        repair_corpus_profile=repair_corpus_profile,
        refresh_corpus=refresh_corpus,
    )
    final_output_dir = Path(output_dir) if output_dir else _default_output_dir(
        repo,
        resolved_trajectory_files,
        repair_corpus_profile,
    )
    resolved_python = python_executable or _resolve_python_executable()
    effective_runtime_import_timeout_s = _resolve_runtime_import_timeout_s(runtime_import_timeout_s)
    preflight_report = _resolve_preflight_report(
        repo=repo,
        python_executable=resolved_python,
        trajectory_files=preflight_trajectory_files,
        include_benchmark_repair_pairs=False,
        extra_args=extra_args,
        runtime_import_timeout_s=effective_runtime_import_timeout_s,
    )
    preflight_report = _annotate_preflight_report_with_requested_python(
        preflight_report,
        python_executable=resolved_python,
    )
    bootstrap_recommendation = _bootstrap_recommendation(
        repo=repo,
        python_executable=resolved_python,
        preflight_report=preflight_report,
    )

    command = [resolved_python, "-m", "scripts.train_rl_repair"]
    for path in resolved_trajectory_files:
        command.extend(["--trajectory-file", path])
    command.extend(["--output-dir", str(final_output_dir)])
    if preflight_only:
        command.append("--preflight-only")
    command.extend(extra_args)

    return {
        "schema": "chattla_tla_prover_local_repair_plan_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "repair_corpus_profile": repair_corpus_profile,
        "refresh_corpus": refresh_corpus,
        "refresh_steps": _refresh_steps(repair_corpus_profile) if refresh_corpus else [],
        "refresh_command": _refresh_command(repair_corpus_profile) if refresh_corpus else None,
        "resolved_trajectory_files": resolved_trajectory_files,
        "preflight_trajectory_files": preflight_trajectory_files,
        "using_merged_default": resolved_trajectory_files == [DEFAULT_MERGED_REPAIR_PAIRS],
        "include_benchmark_repair_pairs": include_benchmark_repair_pairs,
        "preflight_only": preflight_only,
        "preflight_report": preflight_report,
        "python_executable": resolved_python,
        "runtime_import_timeout_s": effective_runtime_import_timeout_s,
        "output_dir": str(final_output_dir),
        "command": command,
        "bootstrap_recommendation": bootstrap_recommendation,
    }


def compact_plan(plan: dict[str, Any]) -> dict[str, Any]:
    preflight_report = dict(plan.get("preflight_report") or {})
    runtime_dependencies = dict(preflight_report.get("runtime_dependencies") or {})
    runtime_missing_modules = [
        str(entry.get("module"))
        for entry in list(runtime_dependencies.get("missing") or [])
        if str(entry.get("module") or "").strip()
    ]
    return {
        "schema": "chattla_tla_prover_local_repair_plan_compact_v1",
        "generated_at": plan.get("generated_at"),
        "repo": plan.get("repo"),
        "repair_corpus_profile": plan.get("repair_corpus_profile"),
        "preflight_only": plan.get("preflight_only"),
        "refresh_corpus": plan.get("refresh_corpus"),
        "using_merged_default": plan.get("using_merged_default"),
        "preflight_trajectory_files": plan.get("preflight_trajectory_files"),
        "python_executable": plan.get("python_executable"),
        "runtime_import_timeout_s": plan.get("runtime_import_timeout_s"),
        "output_dir": plan.get("output_dir"),
        "preflight_ok": preflight_report.get("ok"),
        "local_runtime_ready": runtime_dependencies.get("ok"),
        "runtime_missing_modules": runtime_missing_modules,
        "bootstrap_recommendation": plan.get("bootstrap_recommendation"),
        "model": preflight_report.get("model"),
        "command": plan.get("command"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-file", action="append", default=None)
    parser.add_argument("--include-benchmark-repair-pairs", action="store_true")
    parser.add_argument("--repair-corpus-profile", choices=VALID_PROFILES, default=DEFAULT_PROFILE)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--runtime-import-timeout-s", type=float, default=None)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--refresh-corpus", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    extra_args = list(args.extra_args)
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    plan = build_run_plan(
        repo=REPO,
        trajectory_files=args.trajectory_file,
        include_benchmark_repair_pairs=args.include_benchmark_repair_pairs,
        repair_corpus_profile=args.repair_corpus_profile,
        output_dir=args.output_dir,
        extra_args=extra_args,
        preflight_only=args.preflight,
        refresh_corpus=args.refresh_corpus,
        runtime_import_timeout_s=args.runtime_import_timeout_s,
    )
    payload = compact_plan(plan) if args.compact else plan
    out_path = args.out or DEFAULT_PLAN_OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    if args.refresh_corpus:
        run_refresh_pipeline(repo=REPO, repair_corpus_profile=args.repair_corpus_profile)

    completed = subprocess.run(plan["command"], cwd=REPO)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
