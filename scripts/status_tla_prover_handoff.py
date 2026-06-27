#!/usr/bin/env python3
"""Summarize the ChatTLA TLA prover relay/remote handoff state."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


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
    return {"exists": data is not None, "path": str(path), "data": data}


def _derive_state(
    *,
    launchagent: dict[str, Any],
    submission: dict[str, Any],
    collection: dict[str, Any],
    watch: dict[str, Any],
    decision: dict[str, Any],
    submission_mirror_failed: dict[str, Any],
    handoff_paused: dict[str, Any],
) -> tuple[str, str]:
    submission_data = submission.get("data")
    collection_data = collection.get("data")
    watch_data = watch.get("data")
    decision_data = decision.get("data")
    mirror_failed_data = submission_mirror_failed.get("data")
    paused_data = handoff_paused.get("data")

    if watch_data and watch_data.get("status") == "complete":
        if decision_data and decision_data.get("next_action"):
            verdict = decision_data.get("verdict", "unknown")
            return "results_ready", f"Remote decision verdict={verdict}: {decision_data['next_action']}"
        return "results_ready", "Review known-18 summary and SFT preflight log before deciding the next training/prover step."
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
        return "handoff_paused", f"Remote handoff is paused ({reason}); continue local work or configure another relay."
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

    submission = _report_state(repo / "outputs" / "manifests" / "tla_prover_remote_submission.json")
    collection = _report_state(repo / "outputs" / "manifests" / "tla_prover_remote_results_collection.json")
    watch = _report_state(repo / "outputs" / "manifests" / "tla_prover_remote_watch.json")
    decision = _report_state(repo / "outputs" / "manifests" / "tla_prover_remote_decision.json")
    submission_mirror_failed = _report_state(
        repo / "outputs" / "manifests" / "tla_prover_remote_submission_mirror_failed.json"
    )
    handoff_paused = _report_state(repo / "outputs" / "manifests" / "tla_prover_handoff_paused.json")
    launchagent = _parse_launchctl(launchctl_text)
    state, next_action = _derive_state(
        launchagent=launchagent,
        submission=submission,
        collection=collection,
        watch=watch,
        decision=decision,
        submission_mirror_failed=submission_mirror_failed,
        handoff_paused=handoff_paused,
    )
    submission_data = submission.get("data") or {}
    return {
        "state": state,
        "next_action": next_action,
        "repo": str(repo),
        "launchagent": launchagent,
        "doctor_launchagent": _parse_launchctl(doctor_launchctl_text),
        "mini": _parse_tailscale(tailscale_text),
        "job_ids": {
            "known18_job_id": submission_data.get("known18_job_id"),
            "sft_preflight_job_id": submission_data.get("sft_preflight_job_id"),
        },
        "reports": {
            "submission": submission,
            "collection": collection,
            "watch": watch,
            "decision": decision,
            "submission_mirror_failed": submission_mirror_failed,
            "handoff_paused": handoff_paused,
        },
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
