#!/usr/bin/env python3
"""Write a compact manifest for current TLA prover training/control artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_artifacts_v1.json"

ARTIFACTS = {
    "tlaps_verified_autoprover_traces_v1": {
        "path": "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl",
        "summary": "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json",
        "kind": "verified_tlaps_trace_dataset",
    },
    "chattla_tla_prover_sft_v1": {
        "path": "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
        "summary": "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        "kind": "mixed_prover_sft_dataset",
    },
    "prover_eval_v1": {
        "path": "data/processed/prover_eval.jsonl",
        "summary": "data/processed/prover_eval.summary.json",
        "kind": "verified_tlaps_prover_eval_dataset",
    },
    "sany_tlc_pass_sft_v1": {
        "path": "data/processed/sany_tlc_pass_sft_v1.jsonl",
        "summary": "data/processed/sany_tlc_pass_sft_v1.summary.json",
        "kind": "verified_sany_tlc_pass_sft_dataset",
    },
    "sany_tlc_pass_eval_v1": {
        "path": "data/processed/sany_tlc_pass_eval_v1.jsonl",
        "summary": "data/processed/sany_tlc_pass_eval_v1.summary.json",
        "kind": "heldout_sany_tlc_pass_eval_dataset",
    },
    "sany_tlc_pass_corpus_diagnostic": {
        "path": "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json",
        "kind": "sany_tlc_pass_corpus_quality_gate",
    },
    "known18_module_list": {
        "path": "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
        "kind": "remote_smoke_input",
    },
    "tla_prover_corpus_preflight": {
        "path": "outputs/manifests/tla_prover_corpus_preflight.json",
        "kind": "corpus_schema_preflight_report",
    },
}


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _jsonl_rows(path: Path) -> int | None:
    if not path.exists() or path.suffix != ".jsonl":
        return None
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _read_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact(repo: Path, spec: dict[str, str]) -> dict[str, Any]:
    path = repo / spec["path"]
    summary_path = repo / spec["summary"] if "summary" in spec else None
    item: dict[str, Any] = {
        "kind": spec["kind"],
        "path": spec["path"],
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else None,
        "sha256": _sha256(path),
        "rows": _jsonl_rows(path),
    }
    if summary_path is not None:
        item["summary_path"] = str(summary_path.relative_to(repo))
        item["summary"] = _read_summary(summary_path)
    return item


def build_manifest(repo: Path = REPO) -> dict[str, Any]:
    return {
        "schema": "chattla_tla_prover_artifacts_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo),
        "artifacts": {name: _artifact(repo, spec) for name, spec in ARTIFACTS.items()},
        "remote_next_steps": {
            "known18_pbs": "scripts/qsub_autoprover_known18_corrected_smoke.pbs",
            "known18_launch": "cd ~/ChatTLA && qsub scripts/qsub_autoprover_known18_corrected_smoke.pbs",
            "sft_preflight_pbs": "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
            "sft_preflight_launch": "cd ~/ChatTLA && qsub scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
            "remote_submit_script": "scripts/submit_tla_prover_remote_jobs.sh --submit-sft-preflight",
            "remote_submission_report": "outputs/manifests/tla_prover_remote_submission.json",
            "collect_remote_results": "scripts/collect_tla_prover_remote_results.sh",
            "remote_results_collection_report": "outputs/manifests/tla_prover_remote_results_collection.json",
            "watch_remote_results": "scripts/watch_tla_prover_remote_results.sh",
            "remote_results_watch_report": "outputs/manifests/tla_prover_remote_watch.json",
            "evaluate_remote_results": "python3 scripts/evaluate_tla_prover_remote_results.py",
            "remote_decision_report": "outputs/manifests/tla_prover_remote_decision.json",
            "probe_control_planes": "python3 scripts/probe_tla_prover_control_planes.py",
            "build_tla_prover_eval_corpus": "python3 scripts/build_tla_prover_eval_corpus.py",
            "build_sany_tlc_eval_corpus": "python3 scripts/build_sany_tlc_eval_corpus.py",
            "diagnose_sany_tlc_pass_corpus": "python3 scripts/diagnose_sany_tlc_pass_corpus.py",
            "handoff_status": "python3 scripts/status_tla_prover_handoff.py --live",
            "handoff_doctor": "python3 scripts/doctor_tla_prover_handoff.py --dry-run --live",
            "macmini_known18_handoff": "scripts/sync_macmini_and_submit_known18.sh",
            "macmini_known18_plus_launchagents_handoff": (
                "scripts/sync_macmini_and_submit_known18.sh --install-launchagents"
            ),
            "macmini_known18_plus_sft_preflight_handoff": (
                "scripts/sync_macmini_and_submit_known18.sh --submit-sft-preflight"
            ),
            "wait_for_macmini_then_handoff": (
                "scripts/wait_for_macmini_and_handoff_known18.sh --submit-sft-preflight"
            ),
            "retry_submission_report_mirror": (
                "scripts/wait_for_macmini_and_handoff_known18.sh --mirror-report-only"
            ),
            "install_laptop_wait_handoff_launchagent": (
                "scripts/install_wait_handoff_launchagent.sh --mac-host ericspencer@100.117.97.102"
            ),
            "install_laptop_handoff_doctor_launchagent": (
                "scripts/install_handoff_doctor_launchagent.sh --interval 300"
            ),
            "macmini_launchagents": "scripts/install_macmini_launchagents.sh",
        },
        "promotion_gate": (
            "Do not promote or publish a new model until fresh evals beat or match "
            "base without syntax/module regressions."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    manifest = build_manifest(args.repo)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
