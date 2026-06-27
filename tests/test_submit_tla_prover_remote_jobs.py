import json
import os
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "submit_tla_prover_remote_jobs.sh"
HANDOFF = REPO / "scripts" / "sync_macmini_and_submit_known18.sh"


def test_remote_submit_script_runs_preflight_and_writes_report() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "preflight_tla_prover_remote.py" in text
    assert 'qsub_submit "$PBS_SELECT_KNOWN18" "$PBS_WALLTIME_KNOWN18" scripts/qsub_autoprover_known18_corrected_smoke.pbs' in text
    assert 'qsub_submit "$PBS_SELECT_SFT" "$PBS_WALLTIME_SFT" scripts/qsub_sophia_tla_prover_sft_preflight.pbs' in text
    assert "CHATTLA_PBS_ACCOUNT" in text
    assert "CHATTLA_PBS_QUEUE" in text
    assert "CHATTLA_PBS_FILESYSTEMS" in text
    assert "outputs/manifests/tla_prover_remote_submission.json" in text
    assert "--submit-sft-preflight" in text
    assert "CHATTLA_TLAPM" in text


def test_remote_submit_script_captures_qsub_ids_once(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    qsub_count = tmp_path / "qsub_count"
    qsub = fake_bin / "qsub"
    qsub.write_text(
        f"""#!/usr/bin/env bash
count=$(cat {qsub_count} 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" > {qsub_count}
if [ "$count" = "1" ]; then
  echo "170001.sophia-pbs-01"
else
  echo "170002.sophia-pbs-01"
fi
""",
        encoding="utf-8",
    )
    qsub.chmod(0o755)

    fake_preflight = tmp_path / "preflight.py"
    fake_preflight.write_text("#!/usr/bin/env python3\nprint('{\"ok\": true}')\n", encoding="utf-8")
    fake_preflight.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CHATTLA_REMOTE_PREFLIGHT"] = str(fake_preflight)
    env["CHATTLA_TLAPM"] = str(tmp_path / "tlapm")
    (tmp_path / "tlapm").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (tmp_path / "tlapm").chmod(0o755)

    subprocess.run(
        ["bash", str(SCRIPT), "--repo", str(tmp_path), "--submit-sft-preflight"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    report = json.loads((tmp_path / "outputs/manifests/tla_prover_remote_submission.json").read_text())
    assert report["ok"] is True
    assert report["stage"] == "submitted"
    assert report["repo"] == str(tmp_path)
    assert report["tlapm"] == str(tmp_path / "tlapm")
    assert report["known18_job_id"] == "170001.sophia-pbs-01"
    assert report["sft_preflight_job_id"] == "170002.sophia-pbs-01"
    assert report["known18_qsub_log"] == "outputs/logs/tla_prover_known18_qsub.log"
    assert report["sft_preflight_qsub_log"] == "outputs/logs/tla_prover_sft_preflight_qsub.log"
    assert qsub_count.read_text(encoding="utf-8").strip() == "2"


def test_remote_submit_script_writes_failure_report_on_preflight_error(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    qsub_count = tmp_path / "qsub_count"
    qsub = fake_bin / "qsub"
    qsub.write_text(f"#!/usr/bin/env bash\necho qsub-ran > {qsub_count}\nexit 99\n", encoding="utf-8")
    qsub.chmod(0o755)
    fake_preflight = tmp_path / "preflight.py"
    fake_preflight.write_text("#!/usr/bin/env python3\nprint('bad preflight')\nraise SystemExit(17)\n", encoding="utf-8")
    fake_preflight.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CHATTLA_REMOTE_PREFLIGHT"] = str(fake_preflight)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--repo", str(tmp_path), "--submit-sft-preflight"],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 17
    assert not qsub_count.exists()
    report = json.loads((tmp_path / "outputs/manifests/tla_prover_remote_submission.json").read_text())
    assert report["ok"] is False
    assert report["stage"] == "preflight"
    assert report["exit_code"] == 17
    assert report["known18_job_id"] is None
    assert report["sft_preflight_job_id"] is None


def test_remote_submit_script_writes_failure_report_on_qsub_error(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    qsub = fake_bin / "qsub"
    qsub.write_text("#!/usr/bin/env bash\necho 'queue unavailable' >&2\nexit 42\n", encoding="utf-8")
    qsub.chmod(0o755)
    fake_preflight = tmp_path / "preflight.py"
    fake_preflight.write_text("#!/usr/bin/env python3\nprint('{\"ok\": true}')\n", encoding="utf-8")
    fake_preflight.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CHATTLA_REMOTE_PREFLIGHT"] = str(fake_preflight)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--repo", str(tmp_path)],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 42
    report = json.loads((tmp_path / "outputs/manifests/tla_prover_remote_submission.json").read_text())
    assert report["ok"] is False
    assert report["stage"] == "known18_qsub"
    assert report["exit_code"] == 42
    assert "queue unavailable" in report["error"]
    assert report["known18_job_id"] is None


def test_remote_submit_script_preserves_known18_id_on_sft_qsub_error(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    qsub_count = tmp_path / "qsub_count"
    qsub = fake_bin / "qsub"
    qsub.write_text(
        f"""#!/usr/bin/env bash
count=$(cat {qsub_count} 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" > {qsub_count}
if [ "$count" = "1" ]; then
  echo "170001.sophia-pbs-01"
  exit 0
fi
echo "sft queue unavailable" >&2
exit 43
""",
        encoding="utf-8",
    )
    qsub.chmod(0o755)
    fake_preflight = tmp_path / "preflight.py"
    fake_preflight.write_text("#!/usr/bin/env python3\nprint('{\"ok\": true}')\n", encoding="utf-8")
    fake_preflight.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CHATTLA_REMOTE_PREFLIGHT"] = str(fake_preflight)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--repo", str(tmp_path), "--submit-sft-preflight"],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 43
    report = json.loads((tmp_path / "outputs/manifests/tla_prover_remote_submission.json").read_text())
    assert report["ok"] is False
    assert report["stage"] == "sft_preflight_qsub"
    assert report["known18_job_id"] == "170001.sophia-pbs-01"
    assert report["sft_preflight_job_id"] is None
    assert "sft queue unavailable" in report["error"]


def test_handoff_invokes_remote_submit_script_instead_of_inline_qsub() -> None:
    text = HANDOFF.read_text(encoding="utf-8")

    assert "scripts/submit_tla_prover_remote_jobs.sh" in text
    assert "REMOTE_SUBMIT" in text
    assert "qsub scripts/qsub_autoprover_known18_corrected_smoke.pbs" not in text
