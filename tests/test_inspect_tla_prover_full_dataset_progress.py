import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "inspect_tla_prover_full_dataset_progress.py"


def test_inspect_full_dataset_progress_reports_next_module(tmp_path: Path) -> None:
    first = tmp_path / "First.tla"
    second = tmp_path / "Second.tla"
    third = tmp_path / "Third.tla"
    for path, name in [(first, "First"), (second, "Second"), (third, "Third")]:
        path.write_text(f"---- MODULE {name} ----\n====\n", encoding="utf-8")

    module_list = tmp_path / "modules.txt"
    module_list.write_text("\n".join(str(p) for p in [first, second, third]) + "\n", encoding="utf-8")

    jsonl = tmp_path / "full_dataset_smoke_170004.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps({"module": "First", "module_path": str(first), "status": "skipped"}),
                json.dumps({"module": "Second", "module_path": str(second), "status": "tlaps_partial"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--module-list",
            str(module_list),
            "--jsonl",
            str(jsonl),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["rows_completed"] == 2
    assert payload["next_module"] == str(third)
    assert payload["remaining"] == 1


def test_inspect_full_dataset_progress_reports_status_counts_and_samples(tmp_path: Path) -> None:
    first = tmp_path / "First.tla"
    second = tmp_path / "Second.tla"
    third = tmp_path / "Third.tla"
    for path, name in [(first, "First"), (second, "Second"), (third, "Third")]:
        path.write_text(f"---- MODULE {name} ----\n====\n", encoding="utf-8")

    module_list = tmp_path / "modules.txt"
    module_list.write_text("\n".join(str(p) for p in [first, second, third]) + "\n", encoding="utf-8")

    jsonl = tmp_path / "full_dataset_smoke_170004.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "module": "First",
                        "module_path": str(first),
                        "status": "tlaps_parse_error",
                        "tlapm": {
                            "tier": "parse_error",
                            "errors": ["Error: Could not parse First.tla successfully."],
                        },
                    }
                ),
                json.dumps(
                    {
                        "module": "Second",
                        "module_path": str(second),
                        "status": "tlc_error",
                        "tlc_error": "identifier foo is undefined",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--module-list",
            str(module_list),
            "--jsonl",
            str(jsonl),
            "--sample-status",
            "tlaps_parse_error",
            "--sample-status",
            "tlc_error",
            "--sample-limit",
            "1",
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["status_counts"] == {"tlaps_parse_error": 1, "tlc_error": 1}
    assert payload["status_samples"]["tlaps_parse_error"] == [
        {
            "module": "First",
            "module_path": str(first),
            "status": "tlaps_parse_error",
            "tier": "parse_error",
            "errors": ["Error: Could not parse First.tla successfully."],
            "tlc_error": None,
        }
    ]
    assert payload["status_samples"]["tlc_error"] == [
        {
            "module": "Second",
            "module_path": str(second),
            "status": "tlc_error",
            "tier": None,
            "errors": [],
            "tlc_error": "identifier foo is undefined",
        }
    ]
