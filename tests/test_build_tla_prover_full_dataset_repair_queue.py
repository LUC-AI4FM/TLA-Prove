import json
import subprocess
from pathlib import Path

from scripts.build_tla_prover_full_dataset_repair_queue import build_queue


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_tla_prover_full_dataset_repair_queue.py"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_queue_prioritizes_full_dataset_repair_rows(tmp_path: Path) -> None:
    source = tmp_path / "full_dataset_smoke.jsonl"
    _write_jsonl(
        source,
        [
            {
                "module": "ProofA",
                "module_path": "specs/ProofA.tla",
                "status": "tlaps_partial",
                "runtime_seconds": 12.3,
                "target": "proof",
                "tlapm": {
                    "tier": "partial",
                    "obligations_total": 10,
                    "obligations_proved": 5,
                    "obligations_failed": 5,
                    "errors": ["[ERROR]: 5/10 obligations failed."],
                },
            },
            {
                "module": "ProofB",
                "module_path": "specs/ProofB.tla",
                "status": "tlaps_partial",
                "runtime_seconds": 9.8,
                "target": "proof",
                "tlapm": {
                    "tier": "partial",
                    "obligations_total": 10,
                    "obligations_proved": 7,
                    "obligations_failed": 3,
                    "errors": ["[ERROR]: 3/10 obligations failed."],
                },
            },
            {
                "module": "InductiveA",
                "module_path": "specs/InductiveA.tla",
                "status": "not_inductive",
                "runtime_seconds": 4.5,
                "target": "proof",
                "cti_preview": "Invariant TypeOK is violated.\nState 1: <Initial predicate>",
            },
            {
                "module": "TlcA",
                "module_path": "specs/TlcA.tla",
                "status": "tlc_error",
                "runtime_seconds": 6.2,
                "target": "proof",
                "tlc_error": "TLC produced no conclusive result:\nError: Attempted to apply function.",
            },
            {
                "module": "HarnessA",
                "module_path": "specs/HarnessA.tla",
                "status": "skipped",
                "reason": "typeok_missing_variable_domain_msgs",
                "target": "proof",
            },
            {
                "module": "ContractA",
                "module_path": "specs/ContractA.tla",
                "status": "skipped",
                "reason": "missing_init_next_spec_typeok_vars",
                "target": "proof",
            },
            {
                "module": "SanyA",
                "module_path": "specs/SanyA.tla",
                "status": "skipped",
                "reason": "sany_parse_or_semantic_invalid",
                "target": "proof",
            },
        ],
    )

    rows, summary = build_queue(jsonl_path=source)

    assert [row["module"] for row in rows] == ["ProofA", "ProofB", "InductiveA", "TlcA", "HarnessA"]
    assert [row["repair_priority"] for row in rows] == ["p1", "p1", "p2", "p3", "p4"]
    assert rows[0]["recommended_action"] == "collect_proof_repair_pair"
    assert rows[2]["recommended_action"] == "collect_inductiveness_repair_pair"
    assert rows[3]["recommended_action"] == "collect_tlc_repair_pair"
    assert rows[4]["recommended_action"] == "patch_harness_and_replay"
    assert rows[0]["tlapm"]["obligations_failed"] == 5
    assert rows[2]["failure_excerpt"] == "Invariant TypeOK is violated."
    assert rows[3]["tlc_error_family"] == "function_or_operator_shape"
    assert rows[4]["skip_reason_family"] == "skip_missing_variable_domain"
    assert summary["rows"] == 5
    assert summary["priority_counts"] == {"p1": 2, "p2": 1, "p3": 1, "p4": 1}
    assert summary["repair_bucket_counts"] == {
        "proof_repair": 2,
        "inductiveness_repair": 1,
        "tlc_repair": 1,
        "skip_harness_repair": 1,
    }
    assert summary["excluded_bucket_counts"] == {
        "skip_missing_contract": 1,
        "skip_sany_invalid": 1,
    }


def test_cli_writes_full_dataset_repair_queue(tmp_path: Path) -> None:
    source = tmp_path / "full_dataset_smoke.jsonl"
    out = tmp_path / "repair_queue.jsonl"
    _write_jsonl(
        source,
        [
            {
                "module": "ProofA",
                "module_path": "specs/ProofA.tla",
                "status": "tlaps_partial",
                "runtime_seconds": 12.3,
                "target": "proof",
                "tlapm": {
                    "tier": "partial",
                    "obligations_total": 10,
                    "obligations_proved": 8,
                    "obligations_failed": 2,
                    "errors": ["[ERROR]: 2/10 obligations failed."],
                },
            }
        ],
    )

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--jsonl",
            str(source),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["repair_priority"] == "p1"
    assert payload["rows"] == 1
    assert out.with_suffix(".summary.json").exists()
