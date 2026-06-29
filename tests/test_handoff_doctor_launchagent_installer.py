from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "install_handoff_doctor_launchagent.sh"


def test_handoff_doctor_launchagent_installer_has_periodic_defaults() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "com.chattla.handoff-doctor" in text
    assert "doctor_tla_prover_handoff.py" in text
    assert "StartInterval" in text
    assert "RunAtLoad" in text
    assert "--live" in text
    assert "launchctl bootstrap" in text
    assert "launchctl bootout" in text


def test_handoff_doctor_launchagent_dry_run_prints_plist(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--dry-run",
            "--repo",
            str(REPO),
            "--log-dir",
            str(tmp_path / "logs"),
            "--interval",
            "180",
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "com.chattla.handoff-doctor.plist" in result.stdout
    assert str(REPO / "scripts/doctor_tla_prover_handoff.py") in result.stdout
    assert "<integer>180</integer>" in result.stdout
    assert "handoff_doctor_launchagent.out.log" in result.stdout
