from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "install_wait_handoff_launchagent.sh"


def test_wait_handoff_launchagent_installer_has_safe_defaults() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "com.chattla.wait-for-macmini-handoff" in text
    assert "wait_for_macmini_and_handoff_known18.sh" in text
    assert "RunAtLoad" in text
    assert "KeepAlive" in text
    assert "<false/>" in text
    assert "--submit-sft-preflight" in text
    assert "--dry-run" in text
    assert "launchctl bootstrap" in text
    assert "launchctl bootout" in text


def test_wait_handoff_launchagent_dry_run_prints_plist(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--dry-run",
            "--repo",
            str(REPO),
            "--log-dir",
            str(tmp_path / "logs"),
            "--mac-host",
            "user@relay.example",
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "com.chattla.wait-for-macmini-handoff.plist" in result.stdout
    assert "user@relay.example" in result.stdout
    assert str(REPO / "scripts/wait_for_macmini_and_handoff_known18.sh") in result.stdout
    assert "CHATTLA_HANDOFF_LOG_DIR" in result.stdout


def test_wait_handoff_launchagent_dry_run_accepts_relay_options(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--dry-run",
            "--repo",
            str(REPO),
            "--log-dir",
            str(tmp_path / "logs"),
            "--relay-host",
            "relay.example",
            "--relay-key",
            "/tmp/relay_key",
            "--relay-label",
            "Polaris relay",
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "CHATTLA_RELAY_HOST" in result.stdout
    assert "relay.example" in result.stdout
    assert "CHATTLA_RELAY_KEY" in result.stdout
    assert "/tmp/relay_key" in result.stdout
    assert "CHATTLA_RELAY_LABEL" in result.stdout
    assert "Polaris relay" in result.stdout
