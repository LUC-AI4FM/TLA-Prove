#!/usr/bin/env python3
"""Decide and optionally run the next repair action for the TLA prover handoff."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.status_tla_prover_handoff import REPO, build_status, compact_status


def decide_action(status: dict[str, Any]) -> dict[str, Any]:
    state = status.get("state")
    launch_state = (status.get("launchagent") or {}).get("state")

    if state in {"waiting_for_relay", "waiting_for_macmini"} and launch_state == "running":
        return {
            "action": "noop",
            "reason": "wait LaunchAgent is already running",
            "command": None,
        }
    if state == "handoff_paused":
        return {
            "action": "noop",
            "reason": "remote handoff is paused",
            "command": None,
        }
    if state in {"not_started", "waiting_for_relay", "waiting_for_macmini"}:
        return {
            "action": "install_wait_launchagent",
            "reason": "handoff has not submitted and wait LaunchAgent is not running",
            "command": "scripts/install_wait_handoff_launchagent.sh",
        }
    if state in {"submitted_waiting_for_results", "partial_submit_waiting_for_results", "collecting_results"}:
        return {
            "action": "run_results_watcher",
            "reason": "remote submission exists but final decision evidence is not mirrored",
            "command": "scripts/watch_tla_prover_remote_results.sh",
        }
    if state == "full_smoke_running":
        return {
            "action": "noop",
            "reason": "full-dataset smoke is still running",
            "command": None,
        }
    if state == "submission_mirror_failed":
        return {
            "action": "retry_submission_report_mirror",
            "reason": "remote submit likely completed but local submission report mirror failed",
            "command": "scripts/wait_for_macmini_and_handoff_known18.sh --mirror-report-only",
        }
    if state == "results_ready":
        return {
            "action": "noop",
            "reason": "remote result evidence is ready for review",
            "command": None,
        }
    if state == "remote_submit_failed":
        return {
            "action": "noop",
            "reason": "remote submission failed; inspect submission report before retrying",
            "command": None,
        }
    return {
        "action": "noop",
        "reason": f"no automatic repair for state {state}",
        "command": None,
    }


def _run_command(repo: Path, command: str) -> int:
    result = subprocess.run(command, cwd=repo, shell=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true", default=True)
    parser.add_argument("--no-live", action="store_false", dest="live")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    status = build_status(args.repo, live=args.live)
    decision = decide_action(status)
    payload_status = compact_status(status) if args.compact else status
    payload = {"status": payload_status, "decision": decision, "dry_run": args.dry_run}
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.dry_run or not decision.get("command"):
        return 0
    return _run_command(args.repo, decision["command"])


if __name__ == "__main__":
    raise SystemExit(main())
