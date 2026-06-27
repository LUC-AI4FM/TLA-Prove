from pathlib import Path


INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install_macmini_launchagents.sh"


def test_launchagent_installer_defines_keepalive_agents() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert "com.chattla.codex-goal-supervisor" in text
    assert "com.chattla.tla-prover-autopilot" in text
    assert "<key>KeepAlive</key>" in text
    assert "<key>RunAtLoad</key>" in text
    assert "CHATTLA_REPO" in text
    assert "launchctl bootstrap" in text
    assert "--dry-run" in text
