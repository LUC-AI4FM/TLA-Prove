#!/usr/bin/env python3
"""Run compact local readiness checks for the TLA prover PR surface."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_pr_ready.json"
DEFAULT_EXCLUDE_PREFIXES = ("data/", "outputs/")
DEFAULT_EXCLUDE_FILES = {"memory.md", "docs/formallm.md"}
DEFAULT_UNTRACKED_SCAN_PREFIXES = ("scripts/",)
SYNC_HF_PUBLISH_CORPORA_METADATA_COMMAND = "python3 scripts/sync_hf_publish_corpora_metadata.py"
LOCAL_REPAIR_PLAN_PATH = "outputs/manifests/tla_prover_local_repair_plan.json"
TRACKED_SHARED_ARTIFACTS = (
    "data/processed/ai4fm_public_tlaprove_import_v1.summary.json",
    "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json",
    "data/processed/ai4fm_public_seed_file_manifest_v1.summary.json",
    "data/processed/ai4fm_public_seed_tla_modules_v1.summary.json",
    "data/processed/formalllm_eval_v1.summary.json",
    "data/processed/formalllm_public_module_manifest_v1.summary.json",
    "data/processed/formalllm_public_prover_surface_v1.summary.json",
    "data/processed/ai4fm_public_discovery_manifest_v1.summary.json",
    "data/processed/tla_prover_synthetic_repair_pairs_v1.summary.json",
    "outputs/autoprover/tlaps_verify_published_161016/manifest.json",
    "outputs/autoprover/tlaps_verify_published_161016/summary.json",
    "outputs/manifests/ai4fm_org_surface.json",
    "outputs/manifests/ai4fm_public_dataset_surface.json",
    "outputs/manifests/ai4fm_public_seed_prover_funnel.json",
    "outputs/manifests/ai4fm_public_seed_prover_repair_surface.json",
    "outputs/manifests/ai4fm_public_seed_license_surface.json",
    "outputs/manifests/hf_publish_readiness.json",
    "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
    "outputs/manifests/tla_prover_full_dataset_repair_queue.jsonl",
    "outputs/manifests/tla_prover_full_dataset_repair_queue.summary.json",
    "outputs/manifests/tla_prover_full_dataset_repair_evidence.jsonl",
    "outputs/manifests/tla_prover_full_dataset_repair_evidence.summary.json",
    "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.summary.json",
    "outputs/manifests/ai4fm_public_tlaprove_corpora.json",
    "outputs/manifests/tla_prover_artifacts_v1.json",
    "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
    "outputs/manifests/tla_prover_lane_comparison_plan.json",
    "outputs/manifests/tla_prover_next_experiment.json",
)

SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_tailscale_or_lan_ip", re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b")),
    ("private_ssh_user", re.compile(r"\b" + "eric" + r"spencer@|\b" + "eric" + r"-spencer@")),
    ("private_home_path", re.compile(r"/Users/" + "eric" + r"spencer\b|/home/" + "eric" + r"-spencer\b")),
    ("site_storage_path", re.compile(r"/grand/[A-Za-z0-9_.-]+/")),
    ("fixed_pbs_account", re.compile(r"^#PBS\s+-A\s+EVITA\b", re.MULTILINE)),
    ("private_control_socket", re.compile("codex" + "-sophia")),
    ("specific_compute_node", re.compile(r"sophia-gpu-\d+")),
    ("aisec_specific_host", re.compile("aisec" + r"-102|aisec" + "102")),
]

PY_COMPILE_FILES = [
    "scripts/check_public_dataset_claims.py",
    "scripts/build_ai4fm_public_seed_file_manifest.py",
    "scripts/build_ai4fm_public_seed_license_manifest.py",
    "scripts/build_ai4fm_public_seed_prover_candidates.py",
    "scripts/build_ai4fm_public_seed_prover_shape_corpora.py",
    "scripts/build_ai4fm_public_seed_tla_modules.py",
    "scripts/build_ai4fm_public_tlaprove_import.py",
    "scripts/build_ai4fm_public_discovery_manifest.py",
    "scripts/build_formalllm_public_module_manifest.py",
    "scripts/build_formalllm_public_prover_surface.py",
    "scripts/build_tla_prover_corpus_experiment_matrix.py",
    "scripts/choose_tla_prover_next_experiment.py",
    "scripts/check_tla_prover_pr_ready.py",
    "scripts/inspect_ai4fm_org_surface.py",
    "scripts/inspect_ai4fm_public_dataset_surface.py",
    "scripts/inspect_ai4fm_public_seed_prover_funnel.py",
    "scripts/inspect_ai4fm_public_seed_prover_repair_surface.py",
    "scripts/inspect_ai4fm_public_tlaprove_corpora.py",
    "scripts/materialize_processed_tla_corpus.py",
    "scripts/preflight_tla_prover_remote.py",
    "scripts/probe_tla_prover_control_planes.py",
    "scripts/status_tla_prover_handoff.py",
    "scripts/doctor_tla_prover_handoff.py",
    "scripts/inspect_hf_publish_readiness.py",
    "scripts/build_benchmark_repair_pairs.py",
    "scripts/build_tla_prover_synthetic_repair_pairs.py",
    "scripts/build_tla_prover_repair_corpus.py",
    "scripts/train_rl_repair.py",
    "scripts/build_tla_prover_full_dataset_failure_analysis.py",
    "scripts/build_tla_prover_full_dataset_repair_queue.py",
    "scripts/build_tla_prover_full_dataset_repair_evidence.py",
    "scripts/build_tla_prover_full_dataset_validated_repair_pairs.py",
    "scripts/build_tla_prover_lane_comparison_plan.py",
    "scripts/compare_tla_prover_eval_results.py",
    "scripts/sync_hf_publish_corpora_metadata.py",
    "scripts/upload_v11.py",
    "scripts/train_tla_prover_local.py",
    "scripts/train_tla_prover_repair_local.py",
]

PYTEST_FILES = [
    "tests/test_check_public_dataset_claims.py",
    "tests/test_build_ai4fm_public_seed_file_manifest.py",
    "tests/test_build_ai4fm_public_seed_license_manifest.py",
    "tests/test_build_ai4fm_public_seed_prover_candidates.py",
    "tests/test_build_ai4fm_public_seed_prover_shape_corpora.py",
    "tests/test_build_ai4fm_public_seed_tla_modules.py",
    "tests/test_build_ai4fm_public_tlaprove_import.py",
    "tests/test_build_ai4fm_public_discovery_manifest.py",
    "tests/test_build_formalllm_public_module_manifest.py",
    "tests/test_build_formalllm_public_prover_surface.py",
    "tests/test_check_tla_prover_pr_ready.py",
    "tests/test_inspect_ai4fm_org_surface.py",
    "tests/test_legacy_prover_chunk_pipeline_paths.py",
    "tests/test_inspect_ai4fm_public_tlaprove_corpora.py",
    "tests/test_materialize_processed_tla_corpus.py",
    "tests/test_qsub_sft_preflight.py",
    "tests/test_qsub_fc128_artifact_preflight.py",
    "tests/test_build_tla_prover_corpus_experiment_matrix.py",
    "tests/test_choose_tla_prover_next_experiment.py",
    "tests/test_build_tla_prover_manifest.py",
    "tests/test_prover_diagnostic_fallbacks.py",
    "tests/test_prover_corpus_selection.py",
    "tests/test_train_prover_defaults.py",
    "tests/test_sync_hf_publish_corpora_metadata.py",
    "tests/test_inspect_ai4fm_public_dataset_surface.py",
    "tests/test_inspect_ai4fm_public_seed_prover_funnel.py",
    "tests/test_inspect_ai4fm_public_seed_prover_repair_surface.py",
    "tests/test_inspect_hf_publish_readiness.py",
    "tests/test_sany_validator.py",
    "tests/test_build_benchmark_repair_pairs.py",
    "tests/test_build_tla_prover_synthetic_repair_pairs.py",
    "tests/test_build_tla_prover_repair_corpus.py",
    "tests/test_build_tla_prover_full_dataset_failure_analysis.py",
    "tests/test_build_tla_prover_full_dataset_repair_queue.py",
    "tests/test_build_tla_prover_full_dataset_repair_evidence.py",
    "tests/test_build_tla_prover_full_dataset_validated_repair_pairs.py",
    "tests/test_build_tla_prover_lane_comparison_plan.py",
    "tests/test_compare_tla_prover_eval_results.py",
    "tests/test_upload_v11.py",
    "tests/test_publish_hf.py",
    "tests/test_repair_dataset.py",
    "tests/test_train_rl_repair.py",
    "tests/test_train_tla_prover_local.py",
    "tests/test_train_tla_prover_repair_local.py",
]
SLOW_PYTEST_FILES = [
    "tests/test_collect_tla_prover_remote_results.py",
    "tests/test_preflight_tla_prover_remote.py",
    "tests/test_wait_handoff_launchagent_installer.py",
    "tests/test_status_tla_prover_handoff.py",
    "tests/test_probe_tla_prover_control_planes.py",
    "tests/test_remote_handoff_script.py",
    "tests/test_submit_tla_prover_remote_jobs.py",
    "tests/test_doctor_tla_prover_handoff.py",
]


def tracked_files(repo: Path = REPO) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    paths = []
    for raw in result.stdout.splitlines():
        if raw in DEFAULT_EXCLUDE_FILES:
            continue
        if raw.startswith(DEFAULT_EXCLUDE_PREFIXES):
            continue
        paths.append(repo / raw)
    seen = {path.resolve() for path in paths}
    for rel in TRACKED_SHARED_ARTIFACTS:
        path = repo / rel
        if path.exists() and path.resolve() not in seen:
            paths.append(path)
            seen.add(path.resolve())
    return paths


def readiness_files(repo: Path = REPO, *, include_untracked_scripts: bool = False) -> list[Path]:
    paths = tracked_files(repo)
    if not include_untracked_scripts:
        return paths
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", *DEFAULT_UNTRACKED_SCAN_PREFIXES],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    seen = {path.resolve() for path in paths}
    for raw in result.stdout.splitlines():
        if raw in DEFAULT_EXCLUDE_FILES:
            continue
        if raw.startswith(DEFAULT_EXCLUDE_PREFIXES):
            continue
        path = repo / raw
        resolved = path.resolve()
        if resolved not in seen:
            paths.append(path)
            seen.add(resolved)
    return paths


def scan_files(paths: list[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in SENSITIVE_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        {
                            "path": str(path),
                            "line": line_no,
                            "pattern": name,
                            "text": line.strip()[:240],
                        }
                    )
    return findings


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _compact_bootstrap_recommendation(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {
        key: value.get(key)
        for key in ("reason", "command", "message")
        if key in value
    }
    return compact or None


def _local_repair_runtime_status(repo: Path) -> dict[str, Any]:
    path = repo / LOCAL_REPAIR_PLAN_PATH
    payload = _read_optional_json(path)
    if not isinstance(payload, dict):
        return {"path": LOCAL_REPAIR_PLAN_PATH, "present": False}
    preflight_report = dict(payload.get("preflight_report") or {})
    runtime_dependencies = dict(preflight_report.get("runtime_dependencies") or {})
    runtime_missing_modules = [
        str(entry.get("module"))
        for entry in list(runtime_dependencies.get("missing") or [])
        if str(entry.get("module") or "").strip()
    ]
    return {
        "path": LOCAL_REPAIR_PLAN_PATH,
        "present": True,
        "preflight_ok": preflight_report.get("ok"),
        "local_runtime_ready": runtime_dependencies.get("ok"),
        "runtime_import_timeout_s": payload.get("runtime_import_timeout_s"),
        "runtime_missing_modules": runtime_missing_modules,
        "bootstrap_recommendation": _compact_bootstrap_recommendation(
            payload.get("bootstrap_recommendation")
        ),
    }


def build_commands(*, include_slow_pytest: bool = False) -> list[list[str]]:
    commands = [
        ["python3", "-m", "py_compile", *PY_COMPILE_FILES],
        ["python3", "scripts/check_public_dataset_claims.py"],
        ["python3", "scripts/status_tla_prover_handoff.py", "--no-live", "--compact"],
        ["python3", "scripts/doctor_tla_prover_handoff.py", "--dry-run", "--no-live", "--compact"],
        ["python3", "-m", "pytest", *PYTEST_FILES, "-q"],
    ]
    if include_slow_pytest:
        commands.append(["python3", "-m", "pytest", *SLOW_PYTEST_FILES, "-q"])
    return commands


def run_commands(commands: list[list[str]], *, repo: Path = REPO) -> list[dict[str, Any]]:
    results = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=repo,
            text=True,
            capture_output=True,
        )
        results.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
        )
    return results


def recommended_fixes(
    command_results: list[dict[str, Any]],
    *,
    local_repair_runtime_status: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    fixes: list[dict[str, str]] = []
    for item in command_results:
        command = item.get("command")
        if command == ["python3", "scripts/check_public_dataset_claims.py"] and item.get("returncode") != 0:
            fixes.append(
                {
                    "reason": "HF publish bundle metadata is out of sync with the tracked local source artifacts.",
                    "command": SYNC_HF_PUBLISH_CORPORA_METADATA_COMMAND,
                }
            )
    local_status = dict(local_repair_runtime_status or {})
    bootstrap = dict(local_status.get("bootstrap_recommendation") or {})
    if local_status.get("present") and not local_status.get("local_runtime_ready"):
        fixes.append(
            {
                "reason": "Local repair runtime is not ready on this machine.",
                "command": str(bootstrap.get("command") or LOCAL_REPAIR_PLAN_PATH),
            }
        )
    return fixes


def build_report(
    *,
    repo: Path = REPO,
    run_tests: bool = True,
    include_untracked_scripts: bool = False,
    include_slow_pytest: bool = False,
) -> dict[str, Any]:
    findings = scan_files(readiness_files(repo, include_untracked_scripts=include_untracked_scripts))
    command_results = run_commands(build_commands(include_slow_pytest=include_slow_pytest), repo=repo) if run_tests else []
    commands_ok = all(item["returncode"] == 0 for item in command_results)
    local_repair_runtime_status = _local_repair_runtime_status(repo)
    fixes = recommended_fixes(
        command_results,
        local_repair_runtime_status=local_repair_runtime_status,
    )
    return {
        "ok": not findings and commands_ok,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": ".",
        "scan": {
            "ok": not findings,
            "findings": findings,
            "include_untracked_scripts": include_untracked_scripts,
            "patterns": [name for name, _ in SENSITIVE_PATTERNS],
        },
        "commands": command_results,
        "local_repair_runtime_status": local_repair_runtime_status,
        "recommended_fixes": fixes,
        "slow_pytest_included": include_slow_pytest,
        "slow_pytest_files": SLOW_PYTEST_FILES,
        "tests_ran": run_tests,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument(
        "--include-untracked-scripts",
        action="store_true",
        help="Also scan untracked files under scripts/ for private/site-specific values.",
    )
    parser.add_argument(
        "--include-slow-pytest",
        action="store_true",
        help="Also run the slower remote-handoff pytest slice.",
    )
    args = parser.parse_args()

    report = build_report(
        repo=args.repo,
        run_tests=not args.scan_only,
        include_untracked_scripts=args.include_untracked_scripts,
        include_slow_pytest=args.include_slow_pytest,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
