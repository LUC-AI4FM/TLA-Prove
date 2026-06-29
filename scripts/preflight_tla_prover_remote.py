#!/usr/bin/env python3
"""Preflight a synced ChatTLA checkout before submitting TLA prover jobs."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MODULE_LIST = REPO / "data" / "processed" / "tla_prover" / "tlaps_candidate_modules_18.txt"
DEFAULT_TLAPM = Path(os.environ.get("CHATTLA_TLAPM", "tlapm"))
DEFAULT_PYTHON = Path(os.environ.get("CHATTLA_PYTHON", sys.executable))
from scripts.tla_prover_corpus_paths import (
    DEFAULT_LOCAL_SFT_TRAIN,
    DEFAULT_PUBLIC_SFT_TRAIN,
    resolve_remote_sft_train_file,
)

BASE_REQUIRED = [
    "src/",
    "src/shared/tlc/tla2tools.jar",
    "scripts/autoprover_smoke.py",
    "scripts/summarize_autoprover_smoke.py",
    "scripts/qsub_autoprover_known18_corrected_smoke.pbs",
    "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
    "outputs/manifests/tla_prover_artifacts_v1.json",
    "outputs/manifests/tla_prover_corpus_preflight.json",
]

SFT_REQUIRED = [
    "configs/",
    "data/processed/prover_eval.jsonl",
    "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
    "src/training/train.py",
    "src/training/tlc_eval_callback.py",
]


def _exists(repo: Path, rel_path: str) -> bool:
    return (repo / rel_path.rstrip("/")).exists()


def _read_module_paths(module_list: Path) -> list[str]:
    if not module_list.exists():
        return []
    return [line.strip() for line in module_list.read_text(encoding="utf-8").splitlines() if line.strip()]


def _python_import_timeout_s() -> int:
    return int(os.environ.get("CHATTLA_PYTHON_IMPORT_TIMEOUT", "180"))


def run_preflight(
    *,
    repo: Path = REPO,
    module_list: Path = DEFAULT_MODULE_LIST,
    sft_preflight: bool = False,
    require_tools: bool = False,
    tlapm: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    required = list(BASE_REQUIRED)
    if sft_preflight:
        required.extend(SFT_REQUIRED)

    for rel_path in required:
        if not _exists(repo, rel_path):
            errors.append(f"missing required path: {rel_path}")

    resolved_sft_train = None
    checked_sft_train_paths: list[str] = []
    if sft_preflight:
        resolved_sft_train, checked_sft_train_paths = resolve_remote_sft_train_file(
            repo,
            requested=os.environ.get("CHATTLA_TLA_PROVER_TRAIN_FILE"),
        )
        if resolved_sft_train is None:
            if len(checked_sft_train_paths) == 1:
                errors.append(f"missing required path: {checked_sft_train_paths[0]}")
            else:
                errors.append(
                    "missing required SFT train file; checked: "
                    + ", ".join(checked_sft_train_paths)
                )

    module_paths = _read_module_paths(module_list)
    if not module_paths:
        errors.append(f"module list is empty or missing: {module_list}")
    for raw in module_paths:
        path = repo / raw
        if not path.exists():
            errors.append(f"missing module listed in {module_list.name}: {raw}")

    manifest_path = repo / "outputs" / "manifests" / "tla_prover_artifacts_v1.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid manifest json: {exc}")
        else:
            for name, item in manifest.get("artifacts", {}).items():
                if not item.get("exists"):
                    errors.append(f"manifest artifact missing: {name}")
                if item.get("sha256") is None and item.get("path", "").endswith((".jsonl", ".json", ".txt")):
                    errors.append(f"manifest artifact missing checksum: {name}")

    corpus_preflight = repo / "outputs" / "manifests" / "tla_prover_corpus_preflight.json"
    if corpus_preflight.exists():
        try:
            report = json.loads(corpus_preflight.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid corpus preflight json: {exc}")
        else:
            if not report.get("ok"):
                errors.append("corpus preflight report is not ok")

    if require_tools:
        if shutil.which("java") is None:
            errors.append("java is not on PATH")
        env_tlapm = os.environ.get("CHATTLA_TLAPM")
        candidate = tlapm or (Path(env_tlapm) if env_tlapm else DEFAULT_TLAPM)
        resolved_tlapm = shutil.which(str(candidate)) if not candidate.is_absolute() else None
        if candidate.is_absolute():
            if not candidate.exists():
                errors.append(f"tlapm not found: {candidate}")
            elif not os.access(candidate, os.X_OK):
                errors.append(f"tlapm is not executable: {candidate}")
        elif resolved_tlapm is None:
            errors.append(f"tlapm not found on PATH: {candidate}")
        if sft_preflight:
            py = Path(os.environ.get("CHATTLA_PYTHON", str(DEFAULT_PYTHON)))
            base_model = os.environ.get("CHATTLA_BASE_MODEL", "EricSpencer00/chattla-20b")
            if not py.exists():
                errors.append(f"python not found: {py}")
            elif not os.access(py, os.X_OK):
                errors.append(f"python is not executable: {py}")
            else:
                import_timeout_s = _python_import_timeout_s()
                try:
                    probe = subprocess.run(
                        [
                            str(py),
                            "-c",
                            (
                                "import torch, transformers, datasets, peft, trl, yaml, mlflow; "
                                "import src.training.train"
                            ),
                        ],
                        cwd=repo,
                        text=True,
                        capture_output=True,
                        timeout=import_timeout_s,
                    )
                except subprocess.TimeoutExpired as exc:
                    detail = ((exc.stderr or "").strip() or (exc.stdout or "").strip())
                    message = f"python import probe timed out after {import_timeout_s}s"
                    if detail:
                        message += f": {detail}"
                    errors.append(message)
                else:
                    if probe.returncode != 0:
                        errors.append(
                            "python import probe failed: "
                            + (probe.stderr.strip() or probe.stdout.strip() or f"rc={probe.returncode}")
                        )
            base_path = Path(base_model)
            if (base_path.is_absolute() or base_model.startswith(".")) and not base_path.exists():
                errors.append(f"base model path not found: {base_path}")
            elif base_path.exists() and not (base_path / "config.json").exists():
                errors.append(f"base model config not found: {base_path / 'config.json'}")
    elif shutil.which("java") is None:
        warnings.append("java is not on PATH; use --require-tools on the remote pre-qsub check")

    return {
        "ok": not errors,
        "repo": str(repo),
        "module_list": str(module_list),
        "module_count": len(module_paths),
        "resolved_sft_train_file": resolved_sft_train,
        "sft_preflight": sft_preflight,
        "require_tools": require_tools,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--module-list", type=Path, default=DEFAULT_MODULE_LIST)
    parser.add_argument("--sft-preflight", action="store_true")
    parser.add_argument("--require-tools", action="store_true")
    parser.add_argument("--tlapm", type=Path, default=None)
    args = parser.parse_args()

    report = run_preflight(
        repo=args.repo,
        module_list=args.module_list,
        sft_preflight=args.sft_preflight,
        require_tools=args.require_tools,
        tlapm=args.tlapm,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
