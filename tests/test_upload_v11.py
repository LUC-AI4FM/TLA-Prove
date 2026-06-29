from pathlib import Path
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "upload_v11.py"


def test_upload_v11_is_disabled_and_points_to_publish_hf() -> None:
    result = subprocess.run(
        ["python3", str(SCRIPT)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "disabled" in result.stderr.lower()
    assert "python -m src.training.publish_hf" in result.stderr
