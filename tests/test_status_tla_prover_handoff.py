import json
import subprocess
from pathlib import Path

from scripts.status_tla_prover_handoff import build_status, compact_status


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
    tailscale_text = "203.0.113.10 relay-host user@ linux active; relay \"ord\"; offline, last seen 1h ago"

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


def test_status_reports_direct_sophia_guidance_when_handoff_paused(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_handoff_paused.json").write_text(
        json.dumps({"reason": "Mac mini dead for now"}),
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "handoff_paused"
    assert "sync_sophia_and_submit_known18.sh" in status["next_action"]


def test_status_reports_complete_when_watch_complete(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps(
            {
                "ok": True,
                "known18_job_id": "170001.sophia-pbs-01",
                "sft_preflight_job_id": "170002.sophia-pbs-01",
                "final_proof_verify_job_id": "170003.sophia-pbs-01",
            }
        ),
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
        json.dumps(
            {
                "verdict": "advance",
                "known18_passed": True,
                "proof_artifact_revalidated": True,
                "artifact_verdict": "revalidated",
                "next_action": "Run the full 610-row corrected smoke before SFT.",
            }
        ),
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "results_ready"
    assert status["job_ids"]["known18_job_id"] == "170001.sophia-pbs-01"
    assert status["job_ids"]["sft_preflight_job_id"] == "170002.sophia-pbs-01"
    assert status["job_ids"]["final_proof_verify_job_id"] == "170003.sophia-pbs-01"
    assert status["reports"]["decision"]["data"]["verdict"] == "advance"
    assert status["reports"]["decision"]["data"]["proof_artifact_revalidated"] is True
    assert "Run the full 610-row" in status["next_action"]


def test_status_reports_results_ready_when_decision_exists_without_watch(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps(
            {
                "ok": True,
                "known18_job_id": "170001.sophia-pbs-01",
                "sft_preflight_job_id": "170002.sophia-pbs-01",
                "final_proof_verify_job_id": "170003.sophia-pbs-01",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_decision.json").write_text(
        json.dumps(
            {
                "verdict": "advance",
                "known18_passed": True,
                "proof_artifact_revalidated": True,
                "artifact_verdict": "revalidated",
                "next_action": "Run the full 610-row corrected smoke before SFT.",
            }
        ),
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "results_ready"
    assert status["job_ids"]["final_proof_verify_job_id"] == "170003.sophia-pbs-01"
    assert status["reports"]["watch"]["exists"] is False
    assert "Run the full 610-row" in status["next_action"]


def test_status_reports_full_smoke_running_when_current_job_is_in_qstat_snapshot(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    log_dir = tmp_path / "outputs/logs"
    log_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps(
            {
                "ok": True,
                "known18_job_id": "161009.sophia-pbs-01.lab.alcf.anl.gov",
                "sft_preflight_job_id": "161011.sophia-pbs-01.lab.alcf.anl.gov",
                "final_proof_verify_job_id": "161016.sophia-pbs-01.lab.alcf.anl.gov",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_decision.json").write_text(
        json.dumps(
            {
                "verdict": "advance",
                "known18_passed": True,
                "proof_artifact_revalidated": True,
                "artifact_verdict": "revalidated",
                "next_action": "Run the full 610-row corrected smoke before SFT.",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_qstat.txt").write_text(
        "161018.sophia-pbs-01.lab.alcf.anl.gov eric-sp by-gpu tla_full_smoke -- 1 32 120gb 03:00 R --\n",
        encoding="utf-8",
    )
    (log_dir / "current_sophia_full_dataset_smoke_job.txt").write_text(
        "161018.sophia-pbs-01.lab.alcf.anl.gov\n",
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_full_dataset_progress.json").write_text(
        json.dumps(
            {
                "job_id": "161018.sophia-pbs-01.lab.alcf.anl.gov",
                "rows_so_far": 18,
                "modules_seen": 18,
                "statuses": {
                    "not_inductive": 1,
                    "skipped": 9,
                    "tlaps_partial": 4,
                    "tlc_error": 4,
                },
                "last_completed_module_path": "/tmp/AtomicBakery.tla",
                "last_completed_status": "tlc_error",
                "next_module_path": "/tmp/CausalBroadcast.tla",
            }
        ),
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "full_smoke_running"
    assert status["job_ids"]["full_dataset_smoke_job_id"] == "161018.sophia-pbs-01.lab.alcf.anl.gov"
    assert status["full_dataset_progress"]["rows_so_far"] == 18
    assert status["full_dataset_progress"]["next_module_path"].endswith("CausalBroadcast.tla")
    assert "full-dataset smoke job 161018.sophia-pbs-01.lab.alcf.anl.gov is running" in status["next_action"]


def test_status_merges_full_smoke_note_into_submission_report(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    log_dir = tmp_path / "outputs/logs"
    log_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps(
            {
                "ok": True,
                "known18_job_id": "161009.sophia-pbs-01.lab.alcf.anl.gov",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_submission_full_smoke.json").write_text(
        json.dumps(
            {
                "ok": True,
                "full_dataset_smoke_job_id": "161021.sophia-pbs-01.lab.alcf.anl.gov",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_qstat.txt").write_text(
        "161021.sophia-pbs-01.lab.alcf.anl.gov eric-sp by-gpu tla_full_smoke -- 1 32 120gb 03:00 R --\n",
        encoding="utf-8",
    )
    (log_dir / "current_sophia_full_dataset_smoke_job.txt").write_text(
        "161021.sophia-pbs-01.lab.alcf.anl.gov\n",
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "full_smoke_running"
    assert status["job_ids"]["known18_job_id"] == "161009.sophia-pbs-01.lab.alcf.anl.gov"
    assert status["job_ids"]["full_dataset_smoke_job_id"] == "161021.sophia-pbs-01.lab.alcf.anl.gov"


def test_status_derives_full_smoke_progress_from_local_jsonl_when_manifest_missing(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    log_dir = tmp_path / "outputs/logs"
    log_dir.mkdir(parents=True)
    auto_dir = tmp_path / "outputs/autoprover"
    auto_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps({"ok": True, "full_dataset_smoke_job_id": "161018.sophia-pbs-01.lab.alcf.anl.gov"}),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_qstat.txt").write_text(
        "161018.sophia-pbs-01.lab.alcf.anl.gov eric-sp by-gpu tla_full_smoke -- 1 32 120gb 03:00 R --\n",
        encoding="utf-8",
    )
    (log_dir / "current_sophia_full_dataset_smoke_job.txt").write_text(
        "161018.sophia-pbs-01.lab.alcf.anl.gov\n",
        encoding="utf-8",
    )
    (auto_dir / "full_dataset_smoke_161018.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"module": "A", "status": "skipped"}),
                json.dumps({"module": "B", "status": "tlaps_partial"}),
                json.dumps({"module": "C", "status": "tlc_error"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "full_smoke_running"
    assert status["full_dataset_progress"]["rows_so_far"] == 3
    assert status["full_dataset_progress"]["modules_seen"] == 3
    assert status["full_dataset_progress"]["statuses"] == {
        "skipped": 1,
        "tlaps_partial": 1,
        "tlc_error": 1,
    }


def test_status_ignores_stale_progress_manifest_for_different_full_smoke_job(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    auto_dir = tmp_path / "outputs/autoprover"
    auto_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps({"ok": True, "full_dataset_smoke_job_id": "161021.sophia-pbs-01.lab.alcf.anl.gov"}),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_submission_full_smoke.json").write_text(
        json.dumps({"ok": True, "full_dataset_smoke_job_id": "161021.sophia-pbs-01.lab.alcf.anl.gov"}),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_full_dataset_progress.json").write_text(
        json.dumps({"job_id": "161018.sophia-pbs-01.lab.alcf.anl.gov", "rows_so_far": 610, "modules_seen": 383}),
        encoding="utf-8",
    )
    (auto_dir / "full_dataset_smoke_161021.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"module": "A", "status": "skipped"}),
                json.dumps({"module": "B", "status": "tlaps_partial"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["job_ids"]["full_dataset_smoke_job_id"] == "161021.sophia-pbs-01.lab.alcf.anl.gov"
    assert status["full_dataset_progress"]["rows_so_far"] == 2
    assert status["full_dataset_progress"]["modules_seen"] == 2


def test_status_derives_next_module_path_from_live_jsonl_when_manifest_missing(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs" / "manifests"
    manifest_dir.mkdir(parents=True)
    autoprover_dir = tmp_path / "outputs" / "autoprover"
    autoprover_dir.mkdir(parents=True)

    first = tmp_path / "outputs" / "diamond_gen" / "communication_protocols_work" / "A.tla"
    second = tmp_path / "outputs" / "diamond_gen" / "communication_protocols_work" / "B.tla"
    third = tmp_path / "outputs" / "diamond_gen" / "communication_protocols_work" / "C.tla"
    for path, name in [(first, "A"), (second, "B"), (third, "C")]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---- MODULE {name} ----\n====\n", encoding="utf-8")

    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps({"ok": True, "full_dataset_smoke_job_id": "170004.sophia-pbs-01.lab.alcf.anl.gov"}),
        encoding="utf-8",
    )
    (autoprover_dir / "full_dataset_smoke_170004.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"module": "A", "module_path": str(first), "status": "skipped"}),
                json.dumps({"module": "B", "module_path": str(second), "status": "tlaps_partial"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    status = build_status(tmp_path, live=False)

    assert status["full_dataset_progress"]["rows_so_far"] == 2
    assert status["full_dataset_progress"]["modules_seen"] == 2
    assert status["full_dataset_progress"]["last_completed_module_path"] == str(second)
    assert status["full_dataset_progress"]["next_module_path"] == str(third)


def test_status_prefers_finished_full_smoke_summary_over_stale_qstat_snapshot(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    log_dir = tmp_path / "outputs/logs"
    log_dir.mkdir(parents=True)
    auto_dir = tmp_path / "outputs/autoprover"
    auto_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps(
            {
                "ok": True,
                "known18_job_id": "161009.sophia-pbs-01.lab.alcf.anl.gov",
                "sft_preflight_job_id": "161011.sophia-pbs-01.lab.alcf.anl.gov",
                "final_proof_verify_job_id": "161016.sophia-pbs-01.lab.alcf.anl.gov",
                "full_dataset_smoke_job_id": "161018.sophia-pbs-01.lab.alcf.anl.gov",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_decision.json").write_text(
        json.dumps(
            {
                "verdict": "patch",
                "proof_artifact_revalidated": True,
                "artifact_verdict": "revalidated",
                "next_action": "Do not launch SFT.",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_qstat.txt").write_text(
        "161018.sophia-pbs-01.lab.alcf.anl.gov eric-sp by-gpu tla_full_smoke -- 1 32 120gb 03:00 R --\n",
        encoding="utf-8",
    )
    (log_dir / "current_sophia_full_dataset_smoke_job.txt").write_text(
        "161018.sophia-pbs-01.lab.alcf.anl.gov\n",
        encoding="utf-8",
    )
    (auto_dir / "full_dataset_smoke_161018.summary.json").write_text(
        json.dumps({"job": "161018", "rows": 610, "statuses": {"skipped": 610}}),
        encoding="utf-8",
    )

    status = build_status(tmp_path, launchctl_text="state = exited\n")

    assert status["state"] == "results_ready"
    assert "verdict=patch" in status["next_action"]


def test_compact_status_keeps_only_agent_ready_fields(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps({"ok": True, "known18_job_id": "170001.sophia-pbs-01"}),
        encoding="utf-8",
    )

    compact = compact_status(build_status(tmp_path, launchctl_text="state = exited\n"))

    assert compact["state"] == "submitted_waiting_for_results"
    assert compact["job_ids"]["known18_job_id"] == "170001.sophia-pbs-01"
    assert compact["reports"]["submission"] == "present"
    assert "launchagent" not in compact
    assert "raw_tail" not in json.dumps(compact)


def test_compact_status_carries_artifact_revalidation_flag(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_submission.json").write_text(
        json.dumps(
            {
                "ok": True,
                "known18_job_id": "170001.sophia-pbs-01",
                "final_proof_verify_job_id": "170003.sophia-pbs-01",
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_remote_decision.json").write_text(
        json.dumps(
            {
                "verdict": "advance",
                "proof_artifact_revalidated": True,
                "artifact_verdict": "revalidated",
            }
        ),
        encoding="utf-8",
    )

    compact = compact_status(build_status(tmp_path, launchctl_text="state = exited\n"))

    assert compact["job_ids"]["final_proof_verify_job_id"] == "170003.sophia-pbs-01"
    assert compact["proof_artifact_revalidated"] is True
    assert compact["artifact_verdict"] == "revalidated"


def test_compact_status_carries_full_smoke_progress(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "outputs/manifests"
    manifest_dir.mkdir(parents=True)
    log_dir = tmp_path / "outputs/logs"
    log_dir.mkdir(parents=True)
    (manifest_dir / "tla_prover_remote_qstat.txt").write_text(
        "161018.sophia-pbs-01.lab.alcf.anl.gov eric-sp by-gpu tla_full_smoke -- 1 32 120gb 03:00 R 00:03\n",
        encoding="utf-8",
    )
    (log_dir / "current_sophia_full_dataset_smoke_job.txt").write_text(
        "161018.sophia-pbs-01.lab.alcf.anl.gov\n",
        encoding="utf-8",
    )
    (manifest_dir / "tla_prover_full_dataset_progress.json").write_text(
        json.dumps(
            {
                "job_id": "161018.sophia-pbs-01.lab.alcf.anl.gov",
                "rows_so_far": 18,
                "modules_seen": 18,
                "statuses": {"skipped": 9, "tlaps_partial": 4},
                "last_completed_module_path": "/tmp/AtomicBakery.tla",
                "last_completed_status": "tlaps_partial",
                "next_module_path": "/tmp/CausalBroadcast.tla",
            }
        ),
        encoding="utf-8",
    )

    compact = compact_status(build_status(tmp_path, launchctl_text="state = exited\n"))

    assert compact["state"] == "full_smoke_running"
    assert compact["full_dataset_rows_so_far"] == 18
    assert compact["full_dataset_modules_seen"] == 18
    assert compact["full_dataset_next_module_path"] == "/tmp/CausalBroadcast.tla"


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


def test_status_cli_compact_outputs_small_json() -> None:
    result = subprocess.run(
        ["python3", str(SCRIPT), "--repo", str(REPO), "--no-live", "--compact"],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert "state" in payload
    assert "reports" in payload
    assert "launchagent" not in payload
