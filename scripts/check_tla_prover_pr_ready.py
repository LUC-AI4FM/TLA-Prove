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
    "scripts/check_tla_prover_pr_ready.py",
    "scripts/preflight_tla_prover_remote.py",
    "scripts/probe_tla_prover_control_planes.py",
    "scripts/status_tla_prover_handoff.py",
    "scripts/doctor_tla_prover_handoff.py",
]

PYTEST_FILES = [
    "tests/test_check_tla_prover_pr_ready.py",
    "tests/test_remote_handoff_script.py",
    "tests/test_collect_tla_prover_remote_results.py",
    "tests/test_preflight_tla_prover_remote.py",
    "tests/test_wait_handoff_launchagent_installer.py",
    "tests/test_status_tla_prover_handoff.py",
    "tests/test_probe_tla_prover_control_planes.py",
    "tests/test_submit_tla_prover_remote_jobs.py",
    "tests/test_qsub_sft_preflight.py",
    "tests/test_build_tla_prover_manifest.py",
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


def build_commands() -> list[list[str]]:
    return [
        ["python3", "-m", "py_compile", *PY_COMPILE_FILES],
        ["python3", "scripts/status_tla_prover_handoff.py", "--no-live", "--compact"],
        ["python3", "scripts/doctor_tla_prover_handoff.py", "--dry-run", "--no-live", "--compact"],
        ["python3", "-m", "pytest", *PYTEST_FILES, "-q"],
    ]


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


def build_report(
    *,
    repo: Path = REPO,
    run_tests: bool = True,
    include_untracked_scripts: bool = False,
) -> dict[str, Any]:
    findings = scan_files(readiness_files(repo, include_untracked_scripts=include_untracked_scripts))
    command_results = run_commands(build_commands(), repo=repo) if run_tests else []
    commands_ok = all(item["returncode"] == 0 for item in command_results)
    return {
        "ok": not findings and commands_ok,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "scan": {
            "ok": not findings,
            "findings": findings,
            "include_untracked_scripts": include_untracked_scripts,
            "patterns": [name for name, _ in SENSITIVE_PATTERNS],
        },
        "commands": command_results,
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
    args = parser.parse_args()

    report = build_report(
        repo=args.repo,
        run_tests=not args.scan_only,
        include_untracked_scripts=args.include_untracked_scripts,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
