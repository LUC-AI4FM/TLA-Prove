import json
import subprocess
import sys
from pathlib import Path

from scripts.inspect_tla_prover_repair_reward_surface import build_reward_surface_summary


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_build_reward_surface_summary_reports_oracle_signal(tmp_path: Path) -> None:
    path = tmp_path / "repair.jsonl"
    _write_jsonl(
        path,
        [
            {
                "repair_id": "R1",
                "before_score": 0.05,
                "after_score": 1.0,
                "repair_bucket": "proof_repair",
                "source_file": "benchmark.jsonl",
            },
            {
                "repair_id": "R2",
                "before_score": 0.40,
                "after_score": 0.45,
                "repair_bucket": "proof_repair",
                "source_file": "validated.jsonl",
            },
            {
                "repair_id": "R3",
                "before_score": 0.30,
                "repair_bucket": "tlc_repair",
                "source_file": "validated.jsonl",
            },
        ],
    )

    summary = build_reward_surface_summary(path)

    assert summary["rows"] == 3
    assert summary["rows_with_after_score"] == 2
    assert summary["rows_missing_after_score"] == 1
    assert summary["rows_by_repair_bucket"] == {"proof_repair": 2}
    assert summary["rows_by_source_file"] == {
        "benchmark.jsonl": 1,
        "validated.jsonl": 1,
    }
    assert summary["oracle_reward"]["positive_reward_rows"] == 2
    assert summary["oracle_reward"]["positive_reward_ratio"] == 1.0


def test_cli_writes_reward_surface_summary(tmp_path: Path) -> None:
    path = tmp_path / "repair.jsonl"
    out = tmp_path / "summary.json"
    _write_jsonl(
        path,
        [
            {
                "repair_id": "R1",
                "before_score": 0.05,
                "after_score": 1.0,
                "repair_bucket": "proof_repair",
                "source_file": "benchmark.jsonl",
            }
        ],
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "inspect_tla_prover_repair_reward_surface.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--input",
            str(path),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(result.stdout)
    assert payload["rows"] == 1
    assert payload["oracle_reward"]["positive_reward_rows"] == 1
    assert stdout["oracle_reward"]["positive_reward_rows"] == 1
