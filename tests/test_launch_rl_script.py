from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "launch_rl.sh"


def test_launch_rl_script_prefers_supported_bootstrap_pythons() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "CHATTLA_BOOTSTRAP_PYTHON" in text
    assert "CHATTLA_BOOTSTRAP_REQUIREMENTS_FILE" in text
    assert "SUPPORTED_BOOTSTRAP_PYTHONS=(python3.11 python3.12 python3.13 python3)" in text
    assert "Rebuilding .venv with $bootstrap_python" in text
    assert "\"$bootstrap_python\" -m venv \"$venv_dir\"" in text
