import json
import subprocess
from pathlib import Path

from scripts.evaluate_tla_prover_remote_results import evaluate_known18_summary


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "evaluate_tla_prover_remote_results.py"


def test_evaluator_recommends_advance_for_all_known18_proved() -> None:
    summary = {
        "rows": 18,
        "statuses": {"tlaps_proved": 18},
        "tlaps_checked": 18,
        "tlaps_total_obligations": 180,
        "tlaps_proved_obligations": 180,
        "tlaps_failed_obligations": 0,
    }

    result = evaluate_known18_summary(summary)

    assert result["verdict"] == "advance"
    assert result["known18_passed"] is True
    assert "full 610-row" in result["next_action"]


def test_evaluator_recommends_patch_when_no_tlaps_success() -> None:
    summary = {
        "rows": 18,
        "statuses": {"tlaps_unproved": 18},
        "tlaps_checked": 18,
        "tlaps_total_obligations": 180,
        "tlaps_proved_obligations": 90,
        "tlaps_failed_obligations": 90,
    }

    result = evaluate_known18_summary(summary)

    assert result["verdict"] == "patch"
    assert result["known18_passed"] is False
    assert "Do not launch SFT" in result["next_action"]


def test_evaluator_cli_writes_decision_report(tmp_path: Path) -> None:
    summary_path = tmp_path / "known18.summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "rows": 18,
                "statuses": {"tlaps_partial": 18},
                "tlaps_checked": 18,
                "tlaps_total_obligations": 180,
                "tlaps_proved_obligations": 150,
                "tlaps_failed_obligations": 30,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "decision.json"

    subprocess.run(
        ["python3", str(SCRIPT), "--summary", str(summary_path), "--out", str(out)],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["verdict"] == "advance"
    assert payload["known18_passed"] is True
