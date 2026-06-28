from pathlib import Path
import json
import os
import subprocess


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "collect_tla_prover_direct_results.sh"


def test_collect_direct_results_script_mentions_expected_artifacts() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "--dry-run" in text
    assert "tla_prover_remote_submission.json" in text
    assert "tla_prover_remote_qstat.txt" in text
    assert "known18_corrected_smoke_*" in text
    assert "known18_corrected_smoke_${KNOWN18_JOBNUM}" in text
    assert "autoprover_known18_corrected" in text
    assert "sft_preflight_*.log" in text
    assert "tlaps_verify_published_" in text
    assert "full_dataset_smoke_" in text
    assert "tla_prover_remote_preflight.log" in text
    assert "CHATTLA_REMOTE_PASSWORD" in text
    assert "SOPHIA_PASSWORD" in text
    assert "SSH_ASKPASS_REQUIRE=force" in text
    assert "CHATTLA_REMOTE_SINGLE_SESSION" in text
    assert "ControlMaster" in text
    assert "expect" in text
    assert "rsync" in text
    assert "qstat" in text
    assert "CHATTLA_REMOTE_HOST" in text


def test_collect_direct_results_dry_run_uses_job_ids_from_submission_report(tmp_path: Path) -> None:
    report = tmp_path / "submission.json"
    report.write_text(
        json.dumps(
            {
                "known18_job_id": "170001.sophia-pbs-01",
                "sft_preflight_job_id": "170002.sophia-pbs-01",
                "final_proof_verify_job_id": "170003.sophia-pbs-01",
                "full_dataset_smoke_job_id": "170004.sophia-pbs-01",
                "submit_sft_preflight": True,
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "CHATTLA_REMOTE_HOST": "user@remote.example",
            "CHATTLA_REMOTE_REPO": "~/ChatTLA",
        }
    )
    result = subprocess.run(
        [str(SCRIPT), "--dry-run", "--submission-report", str(report)],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    normalized = result.stdout.replace("\\ ", " ")
    assert "qstat" in normalized
    assert "outputs/autoprover/known18_corrected_smoke_170001.jsonl" in normalized
    assert "outputs/autoprover/known18_corrected_smoke_170001.summary.json" in normalized
    assert "outputs/logs/sft_preflight_170002.log" in normalized
    assert "outputs/logs/tlaps_verify_published_170003.sophia-pbs-01.log" in normalized
    assert "outputs/autoprover/tlaps_verify_published_170003/summary.json" in normalized
    assert "outputs/autoprover/tlaps_verify_published_170003/manifest.json" in normalized
    assert "outputs/autoprover/full_dataset_smoke_170004.jsonl" in normalized
    assert "outputs/autoprover/full_dataset_smoke_170004.summary.json" in normalized
    assert "outputs/manifests/tla_prover_full_dataset_progress.json" in normalized
    assert "outputs/logs/autoprover_full_dataset_smoke_170004.sophia-pbs-01.log" in normalized
    assert "outputs/logs/autoprover_full_dataset_smoke.log" in normalized
    assert "user@remote.example" in normalized


def test_collect_direct_results_writes_error_report_on_transport_failure(tmp_path: Path) -> None:
    report = tmp_path / "submission.json"
    report.write_text(
        json.dumps({"known18_job_id": "170001.sophia-pbs-01", "sft_preflight_job_id": None}),
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name in ["ssh", "rsync"]:
        tool = fake_bin / name
        tool.write_text("#!/usr/bin/env bash\nexit 255\n", encoding="utf-8")
        tool.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CHATTLA_LOCAL_REPO"] = str(tmp_path)
    env["CHATTLA_REMOTE_HOST"] = "user@remote.example"

    result = subprocess.run(
        ["bash", str(SCRIPT), "--submission-report", str(report)],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    collection = json.loads((tmp_path / "outputs/manifests/tla_prover_remote_results_collection.json").read_text())
    assert collection["ok"] is False
    assert any("qstat snapshot failed" in error for error in collection["errors"])
    assert "outputs/autoprover/known18_corrected_smoke_170001.summary.json" in collection["missing"]


def test_collect_direct_results_single_session_uses_expect_when_enabled(tmp_path: Path) -> None:
    report = tmp_path / "submission.json"
    report.write_text(
        json.dumps({"known18_job_id": "170001.sophia-pbs-01", "sft_preflight_job_id": None}),
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    (fake_bin / "ssh").write_text("#!/usr/bin/env bash\nexit 255\n", encoding="utf-8")
    (fake_bin / "rsync").write_text("#!/usr/bin/env bash\nexit 255\n", encoding="utf-8")
    (fake_bin / "expect").write_text(
        "#!/usr/bin/env bash\n"
        "printf 'called\\n' >> \"$EXPECT_LOG\"\n"
        "cat >/dev/null\n"
        "exit 0\n",
        encoding="utf-8",
    )
    for name in ["ssh", "rsync", "expect"]:
        (fake_bin / name).chmod(0o755)

    expect_log = tmp_path / "expect.log"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CHATTLA_LOCAL_REPO"] = str(tmp_path)
    env["CHATTLA_REMOTE_HOST"] = "user@remote.example"
    env["CHATTLA_REMOTE_PASSWORD"] = "one-time"
    env["CHATTLA_REMOTE_SINGLE_SESSION"] = "1"
    env["EXPECT_LOG"] = str(expect_log)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--submission-report", str(report)],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert expect_log.read_text(encoding="utf-8").strip() == "called"
