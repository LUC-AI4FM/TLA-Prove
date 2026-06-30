#!/usr/bin/env python3
"""Summarize the ChatTLA TLA prover relay/remote handoff state."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _display_path(path: Path, repo: Path = REPO) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_error": f"invalid json: {exc}"}


def _tail(path: Path, n: int = 12) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-n:]


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _job_visible_in_qstat(job_id: str, qstat_text: str) -> bool:
    if job_id in qstat_text:
        return True
    prefix = job_id.split(".", 1)[0]
    return prefix in qstat_text


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=5)
    except Exception as exc:  # pragma: no cover - live convenience path
        return str(exc)
    return (result.stdout + result.stderr).strip()


def _parse_launchctl(text: str | None) -> dict[str, Any]:
    if not text:
        return {"available": False}
    state = None
    pid = None
    relay_host = None
    run_interval = None
    for line in text.splitlines():
        if "state =" in line and state is None:
            state = line.split("state =", 1)[1].strip()
        if "pid =" in line and pid is None:
            pid = line.split("pid =", 1)[1].strip()
        if "CHATTLA_RELAY_HOST =>" in line or "CHATTLA_MAC_HOST =>" in line:
            relay_host = line.split("=>", 1)[1].strip()
        if "run interval =" in line and run_interval is None:
            run_interval = line.split("run interval =", 1)[1].strip()
    return {
        "available": True,
        "state": state,
        "pid": pid,
        "relay_host": relay_host,
        "mac_host": relay_host,
        "run_interval": run_interval,
        "raw_tail": text.splitlines()[-12:],
    }


def _parse_tailscale(text: str | None) -> dict[str, Any]:
    if not text:
        return {"available": False}
    line = next(
        (
            item
            for item in text.splitlines()
            if any(token in item.lower() for token in ("relay", "mac-mini", "macmini"))
        ),
        "",
    )
    if not line:
        return {"available": True, "online": None, "raw": text.splitlines()[-12:]}
    return {
        "available": True,
        "online": " offline" not in f" {line.lower()}",
        "line": line,
    }


def _report_state(path: Path) -> dict[str, Any]:
    data = _read_json(path)
    return {"exists": data is not None, "path": _display_path(path), "data": data}


def _merged_report_state(primary: Path, supplement: Path) -> dict[str, Any]:
    primary_state = _report_state(primary)
    supplement_state = _report_state(supplement)
    primary_data = primary_state.get("data")
    supplement_data = supplement_state.get("data")
    if isinstance(primary_data, dict) and primary_data.get("_error"):
        return primary_state
    if isinstance(supplement_data, dict) and supplement_data.get("_error"):
        return primary_state if primary_state.get("exists") else supplement_state
    if not isinstance(primary_data, dict):
        return supplement_state if supplement_state.get("exists") else primary_state
    if not isinstance(supplement_data, dict):
        return primary_state
    merged = dict(primary_data)
    full_smoke_override_keys = {
        "full_dataset_smoke_job_id",
        "full_dataset_smoke_pbs",
        "full_dataset_smoke_qsub_log",
    }
    for key, value in supplement_data.items():
        if key in full_smoke_override_keys and value not in {None, ""}:
            merged[key] = value
        elif key not in merged or merged[key] in {None, ""}:
            merged[key] = value
    state = dict(primary_state)
    state["data"] = merged
    state["supplemental_path"] = _display_path(supplement)
    state["supplement_exists"] = supplement_state.get("exists", False)
    return state


def _derive_full_dataset_progress(
    repo: Path,
    *,
    full_smoke_job_id: str | None,
    manifest_data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if manifest_data and (not full_smoke_job_id or manifest_data.get("job_id") in {None, full_smoke_job_id}):
        return manifest_data
    if not full_smoke_job_id:
        return None
    jobnum = full_smoke_job_id.split(".", 1)[0]
    jsonl_path = repo / "outputs" / "autoprover" / f"full_dataset_smoke_{jobnum}.jsonl"
    if not jsonl_path.exists():
        return None
    try:
        from scripts.sync_tla_prover_full_dataset_progress import _load_rows
        from scripts.autoprover_smoke import _discover, progress_summary
    except Exception:
        return None
    rows = _load_rows(jsonl_path)
    discovered_paths = _discover(
        [
            str(repo / "outputs" / "diamond_gen" / "*_work" / "*.tla"),
            str(repo / "data" / "FormaLLM" / "data" / "*" / "tla" / "*.tla"),
        ],
        limit=0,
    )
    payload = progress_summary(rows, job_id=full_smoke_job_id, discovered_paths=discovered_paths)
    payload["source"] = _display_path(jsonl_path, repo)
    return payload


def _derive_state(
    *,
    launchagent: dict[str, Any],
    submission: dict[str, Any],
    collection: dict[str, Any],
    watch: dict[str, Any],
    decision: dict[str, Any],
    submission_mirror_failed: dict[str, Any],
    handoff_paused: dict[str, Any],
    full_smoke_job_id: str | None,
    qstat_text: str | None,
    full_dataset_summary_exists: bool,
) -> tuple[str, str]:
    submission_data = submission.get("data")
    collection_data = collection.get("data")
    watch_data = watch.get("data")
    decision_data = decision.get("data")
    mirror_failed_data = submission_mirror_failed.get("data")
    paused_data = handoff_paused.get("data")
    if (
        full_smoke_job_id
        and qstat_text
        and _job_visible_in_qstat(full_smoke_job_id, qstat_text)
        and not full_dataset_summary_exists
    ):
        return (
            "full_smoke_running",
            f"Direct Sophia full-dataset smoke job {full_smoke_job_id} is running; wait for outputs/autoprover/full_dataset_smoke_<job>.summary.json before deciding on SFT.",
        )

    if watch_data and watch_data.get("status") == "complete":
        if decision_data and decision_data.get("next_action"):
            verdict = decision_data.get("verdict", "unknown")
            return "results_ready", f"Remote decision verdict={verdict}: {decision_data['next_action']}"
        return "results_ready", "Review known-18 summary and SFT preflight log before deciding the next training/prover step."
    if decision_data and submission_data and decision_data.get("next_action"):
        verdict = decision_data.get("verdict", "unknown")
        return "results_ready", f"Remote decision verdict={verdict}: {decision_data['next_action']}"
    if watch_data and watch_data.get("status") in {"collecting", "timeout"}:
        return "collecting_results", "Run or wait for scripts/watch_tla_prover_remote_results.sh to mirror final job evidence."
    if submission_data:
        if submission_data.get("ok") is False:
            if submission_data.get("known18_job_id"):
                return (
                    "partial_submit_waiting_for_results",
                    "Known-18 was submitted before a later remote-submit failure; run or wait for the watcher to collect known-18 evidence.",
                )
            return "remote_submit_failed", "Inspect outputs/manifests/tla_prover_remote_submission.json and the stage log named there."
        return "submitted_waiting_for_results", "Wait for the watcher/collector to mirror known-18 summary and SFT preflight log."
    if mirror_failed_data:
        return (
            "submission_mirror_failed",
            "Remote submit likely completed but the local submission report mirror failed; retry mirror-only before any resubmission.",
        )
    if paused_data:
        reason = paused_data.get("reason", "handoff route paused")
        return (
            "handoff_paused",
            (
                f"Remote handoff is paused ({reason}); continue local work or use "
                "scripts/sync_sophia_and_submit_known18.sh for the direct Sophia lane."
            ),
        )
    if launchagent.get("state") == "running":
        return "waiting_for_relay", "Wait hook is active; leave LaunchAgent running until relay SSH becomes reachable."
    if collection_data and collection_data.get("errors"):
        return "collection_error", "Inspect outputs/manifests/tla_prover_remote_results_collection.json."
    return "not_started", "Install or kickstart the wait handoff LaunchAgent, or run the handoff manually once the relay is reachable."


def build_status(
    repo: Path = REPO,
    *,
    launchctl_text: str | None = None,
    doctor_launchctl_text: str | None = None,
    tailscale_text: str | None = None,
    live: bool = False,
) -> dict[str, Any]:
    repo = Path(repo)
    if live and launchctl_text is None:
        launchctl_text = _run(["launchctl", "print", f"gui/{subprocess.getoutput('id -u')}/com.chattla.wait-for-macmini-handoff"])
    if live and doctor_launchctl_text is None:
        doctor_launchctl_text = _run(["launchctl", "print", f"gui/{subprocess.getoutput('id -u')}/com.chattla.handoff-doctor"])
    if live and tailscale_text is None:
        tailscale_text = _run(["tailscale", "status"])

    submission = _merged_report_state(
        repo / "outputs" / "manifests" / "tla_prover_remote_submission.json",
        repo / "outputs" / "manifests" / "tla_prover_remote_submission_full_smoke.json",
    )
    collection = _report_state(repo / "outputs" / "manifests" / "tla_prover_remote_results_collection.json")
    watch = _report_state(repo / "outputs" / "manifests" / "tla_prover_remote_watch.json")
    decision = _report_state(repo / "outputs" / "manifests" / "tla_prover_remote_decision.json")
    submission_mirror_failed = _report_state(
        repo / "outputs" / "manifests" / "tla_prover_remote_submission_mirror_failed.json"
    )
    handoff_paused = _report_state(repo / "outputs" / "manifests" / "tla_prover_handoff_paused.json")
    full_smoke_job_id = None
    full_smoke_job_path = repo / "outputs" / "logs" / "current_sophia_full_dataset_smoke_job.txt"
    if submission.get("data") and (submission.get("data") or {}).get("full_dataset_smoke_job_id"):
        full_smoke_job_id = (submission.get("data") or {}).get("full_dataset_smoke_job_id")
    elif full_smoke_job_path.exists():
        full_smoke_job_id = full_smoke_job_path.read_text(encoding="utf-8", errors="replace").strip() or None
    full_dataset_progress_report = _report_state(repo / "outputs" / "manifests" / "tla_prover_full_dataset_progress.json")
    full_dataset_progress_data = _derive_full_dataset_progress(
        repo,
        full_smoke_job_id=full_smoke_job_id,
        manifest_data=full_dataset_progress_report.get("data"),
    )
    full_dataset_summary_exists = False
    if full_smoke_job_id:
        jobnum = full_smoke_job_id.split(".", 1)[0]
        full_dataset_summary_exists = (
            repo / "outputs" / "autoprover" / f"full_dataset_smoke_{jobnum}.summary.json"
        ).exists()
    qstat_text = _read_text(repo / "outputs" / "manifests" / "tla_prover_remote_qstat.txt")
    launchagent = _parse_launchctl(launchctl_text)
    state, next_action = _derive_state(
        launchagent=launchagent,
        submission=submission,
        collection=collection,
        watch=watch,
        decision=decision,
        submission_mirror_failed=submission_mirror_failed,
        handoff_paused=handoff_paused,
        full_smoke_job_id=full_smoke_job_id,
        qstat_text=qstat_text,
        full_dataset_summary_exists=full_dataset_summary_exists,
    )
    submission_data = submission.get("data") or {}
    return {
        "state": state,
        "next_action": next_action,
        "repo": _display_path(repo, repo),
        "launchagent": launchagent,
        "doctor_launchagent": _parse_launchctl(doctor_launchctl_text),
        "mini": _parse_tailscale(tailscale_text),
        "job_ids": {
            "known18_job_id": submission_data.get("known18_job_id"),
            "sft_preflight_job_id": submission_data.get("sft_preflight_job_id"),
            "final_proof_verify_job_id": submission_data.get("final_proof_verify_job_id"),
            "full_dataset_smoke_job_id": full_smoke_job_id,
        },
        "reports": {
            "submission": submission,
            "collection": collection,
            "watch": watch,
            "decision": decision,
            "full_dataset_progress": {
                "exists": full_dataset_progress_data is not None,
                "path": _display_path(repo / "outputs" / "manifests" / "tla_prover_full_dataset_progress.json", repo),
                "data": full_dataset_progress_data,
            },
            "submission_mirror_failed": submission_mirror_failed,
            "handoff_paused": handoff_paused,
        },
        "full_dataset_progress": full_dataset_progress_data,
        "wait_log_tail": _tail(repo / "outputs" / "logs" / "wait_for_macmini_handoff.log"),
    }


def _report_presence(report: dict[str, Any]) -> str:
    if not report.get("exists"):
        return "missing"
    data = report.get("data")
    if isinstance(data, dict) and data.get("_error"):
        return "invalid"
    return "present"


def compact_status(status: dict[str, Any]) -> dict[str, Any]:
    reports = status.get("reports") or {}
    decision_data = (reports.get("decision") or {}).get("data") or {}
    submission_data = (reports.get("submission") or {}).get("data") or {}
    collection_data = (reports.get("collection") or {}).get("data") or {}
    watch_data = (reports.get("watch") or {}).get("data") or {}
    full_dataset_progress = status.get("full_dataset_progress") or {}
    return {
        "state": status.get("state"),
        "next_action": status.get("next_action"),
        "repo": status.get("repo"),
        "job_ids": status.get("job_ids") or {},
        "reports": {name: _report_presence(report) for name, report in reports.items()},
        "submission_stage": submission_data.get("stage"),
        "collection_missing": len(collection_data.get("missing") or []),
        "collection_errors": len(collection_data.get("errors") or []),
        "watch_status": watch_data.get("status"),
        "verdict": decision_data.get("verdict"),
        "proof_artifact_revalidated": decision_data.get("proof_artifact_revalidated"),
        "artifact_verdict": decision_data.get("artifact_verdict"),
        "full_dataset_rows_so_far": full_dataset_progress.get("rows_so_far"),
        "full_dataset_modules_seen": full_dataset_progress.get("modules_seen"),
        "full_dataset_next_module_path": full_dataset_progress.get("next_module_path"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--live", action="store_true", default=True)
    parser.add_argument("--no-live", action="store_false", dest="live")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    status = build_status(args.repo, live=args.live)
    payload = compact_status(status) if args.compact else status
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
