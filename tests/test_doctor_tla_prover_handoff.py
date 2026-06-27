import json
import subprocess
from pathlib import Path

from scripts.doctor_tla_prover_handoff import decide_action


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "doctor_tla_prover_handoff.py"


def test_doctor_decides_noop_when_wait_hook_running() -> None:
    status = {"state": "waiting_for_macmini", "launchagent": {"state": "running"}}

    decision = decide_action(status)

    assert decision["action"] == "noop"
    assert "already running" in decision["reason"]


def test_doctor_decides_install_when_wait_hook_not_started() -> None:
    status = {"state": "not_started", "launchagent": {"state": None}}

    decision = decide_action(status)

    assert decision["action"] == "install_wait_launchagent"
    assert "install_wait_handoff_launchagent.sh" in decision["command"]


def test_doctor_decides_watch_when_submission_exists() -> None:
    status = {"state": "submitted_waiting_for_results", "launchagent": {"state": "exited"}}

    decision = decide_action(status)

    assert decision["action"] == "run_results_watcher"
    assert "watch_tla_prover_remote_results.sh" in decision["command"]


def test_doctor_decides_watch_when_partial_submit_has_known18_job() -> None:
    status = {
        "state": "partial_submit_waiting_for_results",
        "launchagent": {"state": "exited"},
        "job_ids": {"known18_job_id": "170001.sophia-pbs-01"},
    }

    decision = decide_action(status)

    assert decision["action"] == "run_results_watcher"
    assert "watch_tla_prover_remote_results.sh" in decision["command"]


def test_doctor_decides_mirror_only_when_submission_mirror_failed() -> None:
    status = {"state": "submission_mirror_failed", "launchagent": {"state": "exited"}}

    decision = decide_action(status)

    assert decision["action"] == "retry_submission_report_mirror"
    assert "wait_for_macmini_and_handoff_known18.sh --mirror-report-only" in decision["command"]


def test_doctor_noops_when_handoff_paused() -> None:
    status = {"state": "handoff_paused", "launchagent": {"state": None}}

    decision = decide_action(status)

    assert decision["action"] == "noop"
    assert "paused" in decision["reason"]


def test_doctor_cli_dry_run_outputs_decision() -> None:
    result = subprocess.run(
        ["python3", str(SCRIPT), "--repo", str(REPO), "--dry-run", "--no-live"],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert "status" in payload
    assert "decision" in payload
    assert "action" in payload["decision"]


def test_doctor_cli_compact_outputs_small_decision_packet() -> None:
    result = subprocess.run(
        ["python3", str(SCRIPT), "--repo", str(REPO), "--dry-run", "--no-live", "--compact"],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert "status" in payload
    assert "decision" in payload
    assert "launchagent" not in payload["status"]
    assert "action" in payload["decision"]
