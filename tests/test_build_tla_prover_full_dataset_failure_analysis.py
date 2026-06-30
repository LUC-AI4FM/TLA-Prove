import json
import subprocess
from pathlib import Path

from scripts.build_tla_prover_full_dataset_failure_analysis import build_failure_analysis


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_tla_prover_full_dataset_failure_analysis.py"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_failure_analysis_classifies_action_buckets(tmp_path: Path) -> None:
    jsonl = tmp_path / "full_dataset_smoke.jsonl"
    summary = tmp_path / "full_dataset_smoke.summary.json"
    _write_jsonl(
        jsonl,
        [
            {
                "module": "ReplayReady",
                "module_path": "specs/ReplayReady.tla",
                "status": "no_tlapm",
            },
            {
                "module": "ProofA",
                "module_path": "specs/ProofA.tla",
                "status": "tlaps_partial",
                "tlapm": {"obligations_failed": 3, "obligations_proved": 7, "obligations_total": 10},
            },
            {
                "module": "InductiveA",
                "module_path": "specs/InductiveA.tla",
                "status": "not_inductive",
                "cti_preview": "Invariant TypeOK is violated.",
            },
            {
                "module": "TlcA",
                "module_path": "specs/TlcA.tla",
                "status": "tlc_error",
                "tlc_error": "TLC produced no conclusive result:\nError: Deadlock reached.",
            },
            {
                "module": "SkipHarness",
                "module_path": "specs/SkipHarness.tla",
                "status": "skipped",
                "reason": "typeok_missing_variable_domain_msgs",
            },
            {
                "module": "SkipContract",
                "module_path": "specs/SkipContract.tla",
                "status": "skipped",
                "reason": "missing_init_next_spec_typeok_vars",
            },
            {
                "module": "SkipSany",
                "module_path": "specs/SkipSany.tla",
                "status": "skipped",
                "reason": "sany_parse_or_semantic_invalid",
                "sany_errors": ["bad parse"],
            },
        ],
    )
    summary.write_text(json.dumps({"job": "170004", "rows": 6, "statuses": {"skipped": 3}}), encoding="utf-8")

    payload = build_failure_analysis(jsonl_path=jsonl, summary_path=summary, sample_limit=2)

    assert payload["job_id"] == "170004"
    assert payload["action_bucket_counts"] == {
        "proof_replay_ready": 1,
        "proof_repair": 1,
        "inductiveness_repair": 1,
        "tlc_repair": 1,
        "skip_harness_repair": 1,
        "skip_missing_contract": 1,
        "skip_sany_invalid": 1,
        "skip_other": 0,
    }
    assert payload["immediate_repair_rows"] == 5
    assert payload["skip_reason_families"]["skip_missing_contract_operators"] == 1
    assert payload["top_tlaps_partial_by_failed_obligations"][0]["module"] == "ProofA"
    assert payload["action_bucket_samples"]["skip_sany_invalid"][0]["sany_errors"] == ["bad parse"]


def test_build_failure_analysis_cli_writes_manifest(tmp_path: Path) -> None:
    jsonl = tmp_path / "full_dataset_smoke.jsonl"
    summary = tmp_path / "full_dataset_smoke.summary.json"
    out = tmp_path / "failure_analysis.json"
    _write_jsonl(
        jsonl,
        [
            {
                "module": "ReplayReady",
                "module_path": "specs/ReplayReady.tla",
                "status": "skeleton_emitted",
            },
            {
                "module": "ProofA",
                "module_path": "specs/ProofA.tla",
                "status": "tlaps_partial",
                "tlapm": {"obligations_failed": 1, "obligations_proved": 9, "obligations_total": 10},
            },
            {
                "module": "SkipHarness",
                "module_path": "specs/SkipHarness.tla",
                "status": "skipped",
                "reason": "typeok_uses_unbounded_seq",
            },
        ],
    )
    summary.write_text(json.dumps({"job": "170004", "rows": 2, "statuses": {"tlaps_partial": 1, "skipped": 1}}), encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--jsonl",
            str(jsonl),
            "--summary",
            str(summary),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["source_jsonl"] == str(jsonl)
    assert payload["source_summary"] == str(summary)
    assert payload["action_bucket_counts"]["proof_replay_ready"] == 1
    assert payload["action_bucket_counts"]["proof_repair"] == 1
    assert payload["action_bucket_counts"]["skip_harness_repair"] == 1
