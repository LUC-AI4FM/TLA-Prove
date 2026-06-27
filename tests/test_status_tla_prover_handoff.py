import json
import subprocess
from pathlib import Path

from scripts.status_tla_prover_handoff import build_status


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "status_tla_prover_handoff.py"


def test_status_reports_waiting_for_mini_without_submission(tmp_path: Path) -> None:
    log_dir = tmp_path / "outputs/logs"
    log_dir.mkdir(parents=True)
    (log_dir / "wait_for_macmini_handoff.log").write_text(
        "[2026-06-27T14:46:42Z] relay not reachable attempt=1; retrying in 60s\n",
        encoding="utf-8",
    )
    launchctl_text = """
state = running
pid = 37655
CHATTLA_RELAY_HOST => user@relay.example
"""
    tailscale_text = "100.64.0.10 relay-host user@ linux active; relay \"ord\"; offline, last seen 1h ago"

    doctor_launchctl_text = """
state = not running
run interval = 300 seconds
"""

    status = build_status(
        tmp_path,
        launchctl_text=launchctl_text,
        doctor_launchctl_text=doctor_launchctl_text,
        tailscale_text=tailscale_text,
    )

    assert status["state"] == "waiting_for_relay"
    assert status["launchagent"]["state"] == "running"
    assert status["launchagent"]["pid"] == "37655"
    assert status["doctor_launchagent"]["state"] == "not running"
    assert status["doctor_launchagent"]["run_interval"] == "300 seconds"
    assert status["mini"]["online"] is False
    assert status["reports"]["submission"]["exists"] is False
    assert "Wait hook is active" in status["next_action"]


def test_status_reports_complete_when_watch_complete(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps({"ok": True, "known18_job_id": "170001.sophia-pbs-01", "sft_preflight_job_id": "170002.sophia-pbs-01"}),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_results_collection.json").write_text(
        json.dumps({"ok": True, "missing": [], "errors": []}),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_watch.json").write_text(
        json.dumps({"status": "complete", "attempts": 3}),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_decision.json").write_text(
        json.dumps({"verdict": "advance", "known18_passed": True, "next_action": "Run the full 610-row corrected smoke before SFT."}),
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "results_ready"
    assert status["job_ids"]["known18_job_id"] == "170001.sophia-pbs-01"
    assert status["job_ids"]["sft_preflight_job_id"] == "170002.sophia-pbs-01"
    assert status["reports"]["decision"]["data"]["verdict"] == "advance"
    assert "Run the full 610-row" in status["next_action"]


def test_status_reports_partial_submit_when_known18_was_launched(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps(
            {
                "ok": False,
                "stage": "sft_preflight_qsub",
                "known18_job_id": "170001.sophia-pbs-01",
                "sft_preflight_job_id": None,
            }
        ),
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "partial_submit_waiting_for_results"
    assert status["job_ids"]["known18_job_id"] == "170001.sophia-pbs-01"
    assert "known-18" in status["next_action"]


def test_status_reports_submission_mirror_failed_sentinel(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission_mirror_failed.json").write_text(
        json.dumps({"stage": "mirror_remote_report", "exit_code": 76}),
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "submission_mirror_failed"
    assert status["reports"]["submission_mirror_failed"]["exists"] is True
    assert "mirror-only" in status["next_action"]


def test_status_reports_handoff_paused(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_handoff_paused.json").write_text(
        json.dumps({"reason": "Mac mini dead for now"}),
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "handoff_paused"
    assert status["reports"]["handoff_paused"]["exists"] is True
    assert "local" in status["next_action"]


def test_status_cli_outputs_json() -> None:
    result = subprocess.run(
        ["python3", str(SCRIPT), "--repo", str(REPO), "--no-live"],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert "state" in payload
    assert "reports" in payload
    assert "next_action" in payload
