from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SUPERVISOR = REPO / "scripts" / "macmini_codex_goal_supervisor.sh"
AUTOPILOT = REPO / "scripts" / "macmini_tla_prover_autopilot.sh"


def test_codex_supervisor_has_preflight_pid_status_and_log_rotation() -> None:
    text = SUPERVISOR.read_text(encoding="utf-8")

    assert 'REPO="${CHATTLA_REPO:-$HOME/GitHub/ChatTLA/ChatTLA}"' in text
    assert 'CODEX="${CODEX_BIN:-$HOME/.local/bin/codex}"' in text
    assert "PIDFILE=" in text
    assert "STATUS=" in text
    assert "preflight()" in text
    assert "rotate_log()" in text
    assert "write_status()" in text
    assert "worker_running()" in text
    assert "sha256" in text


def test_macmini_autopilot_uses_home_defaults_and_status_file() -> None:
    text = AUTOPILOT.read_text(encoding="utf-8")

    assert 'REPO="${CHATTLA_REPO:-$HOME/GitHub/ChatTLA/ChatTLA}"' in text
    assert "STATUS=" in text
    assert "write_status()" in text
    assert "rotate_log()" in text
    assert "SOPHIA_CTL=" in text
