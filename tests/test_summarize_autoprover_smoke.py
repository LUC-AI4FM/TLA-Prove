import json
import subprocess
from pathlib import Path

from scripts.summarize_autoprover_smoke import summarize


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "summarize_autoprover_smoke.py"


def test_summarize_groups_tlc_error_families_and_samples() -> None:
    rows = [
        {
            "module": "DeadlockA",
            "module_path": "a/DeadlockA.tla",
            "status": "tlc_error",
            "tlc_error": "TLC produced no conclusive result:\nError: Deadlock reached.\nState 1",
        },
        {
            "module": "InitBad",
            "module_path": "a/InitBad.tla",
            "status": "tlc_error",
            "tlc_error": "Error: current state is not a legal state\nWhile working on the initial state:",
        },
        {
            "module": "ChannelMissing",
            "module_path": "a/ChannelMissing.tla",
            "status": "tlc_error",
            "tlc_error": "Error: In evaluation, the identifier channel is either undefined or not an operator.",
        },
        {
            "module": "ParseBad",
            "module_path": "a/ParseBad.tla",
            "status": "tlc_error",
            "tlc_error": "***Parse Error***\nFatal errors while parsing TLA+ spec in file ParseBad\n*** Errors: 1\nError: Parsing or semantic analysis failed.",
        },
        {
            "module": "GoalUnset",
            "module_path": "a/GoalUnset.tla",
            "status": "tlc_error",
            "tlc_error": "Error: The constant parameter Goal is not assigned a value by the configuration file.",
        },
        {
            "module": "PartialProof",
            "module_path": "a/PartialProof.tla",
            "status": "tlaps_partial",
            "tlapm": {"tier": "partial", "obligations_proved": 7, "obligations_total": 10, "obligations_failed": 3},
        },
    ]

    payload = summarize(rows)

    assert payload["tlc_error_families"] == {
        "tlc_error_deadlock": 1,
        "tlc_error_illegal_init_state": 1,
        "tlc_error_missing_identifier:channel": 1,
        "tlc_error_parse_or_semantic": 1,
        "tlc_error_unassigned_constant": 1,
    }
    assert payload["tlc_error_samples"]["tlc_error_deadlock"][0]["module"] == "DeadlockA"
    assert payload["tlc_error_samples"]["tlc_error_illegal_init_state"][0]["module_path"] == "a/InitBad.tla"
    assert payload["tlc_error_samples"]["tlc_error_missing_identifier:channel"][0]["tlc_error"].startswith(
        "Error: In evaluation"
    )
    assert payload["tlc_error_samples"]["tlc_error_parse_or_semantic"][0]["module"] == "ParseBad"
    assert payload["tlc_error_samples"]["tlc_error_unassigned_constant"][0]["module"] == "GoalUnset"


def test_summarize_cli_writes_tlc_error_families(tmp_path: Path) -> None:
    jsonl = tmp_path / "smoke.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "module": "DeadlockA",
                        "module_path": "a/DeadlockA.tla",
                        "status": "tlc_error",
                        "tlc_error": "TLC produced no conclusive result:\nError: Deadlock reached.\nState 1",
                    }
                ),
                json.dumps(
                    {
                        "module": "PartialProof",
                        "module_path": "a/PartialProof.tla",
                        "status": "tlaps_partial",
                        "tlapm": {
                            "tier": "partial",
                            "obligations_proved": 7,
                            "obligations_total": 10,
                            "obligations_failed": 3,
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "summary.json"

    subprocess.run(
        ["python3", str(SCRIPT), str(jsonl), "--out", str(out)],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["tlc_error_families"] == {"tlc_error_deadlock": 1}
    assert payload["tlc_error_samples"]["tlc_error_deadlock"][0]["module"] == "DeadlockA"
