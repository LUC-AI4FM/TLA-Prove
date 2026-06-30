import json
import subprocess
import sys
from pathlib import Path

from scripts.build_tla_prover_patch_worklist import build_worklist


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_tla_prover_patch_worklist.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def test_build_worklist_prioritizes_pair_ready_patch_targets(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "repair_queue.jsonl",
        [
            {
                "module": "AtomicRegister",
                "module_path": "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "recommended_action": "collect_proof_repair_pair",
                "status": "tlaps_partial",
                "failure_excerpt": "[ERROR]: Could not prove or check:",
                "tlapm": {"obligations_failed": 3, "obligations_total": 10},
            },
            {
                "module": "Arp",
                "module_path": "outputs/diamond_gen/communication_protocols_work/Arp.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "recommended_action": "collect_proof_repair_pair",
                "status": "tlaps_partial",
                "failure_excerpt": "[ERROR]: Could not prove or check:",
                "tlapm": {"obligations_failed": 2, "obligations_total": 10},
            },
            {
                "module": "Barrier",
                "module_path": "outputs/diamond_gen/synchronization_work/Barrier.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "recommended_action": "collect_proof_repair_pair",
                "status": "tlaps_partial",
                "failure_excerpt": "[ERROR]: Could not prove or check:",
                "tlapm": {"obligations_failed": 1, "obligations_total": 10},
            },
            {
                "module": "CopyingGc",
                "module_path": "outputs/diamond_gen/memory_caches_work/CopyingGc.tla",
                "repair_bucket": "inductiveness_repair",
                "repair_priority": "p2",
                "recommended_action": "collect_inductiveness_repair_pair",
                "status": "not_inductive",
                "failure_excerpt": "Invariant TypeOK is violated.",
            },
            {
                "module": "AlternatingBit",
                "module_path": "outputs/diamond_gen/networking_work/AlternatingBit.tla",
                "repair_bucket": "skip_harness_repair",
                "repair_priority": "p4",
                "recommended_action": "patch_harness_and_replay",
                "status": "skipped",
                "failure_excerpt": "missing variable domain",
                "skip_reason_family": "skip_missing_variable_domain",
            },
        ],
    )
    _write_jsonl(
        tmp_path / "repair_evidence.jsonl",
        [
            {
                "module": "AtomicRegister",
                "module_path": "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "before_score": 0.7,
                "prompt_source_kind": "diamond_eval_holdout",
                "gold_source_kind": "diamond_eval_holdout",
            },
            {
                "module": "Arp",
                "module_path": "outputs/diamond_gen/communication_protocols_work/Arp.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "before_score": 0.8,
                "prompt_source_kind": "diamond_eval_holdout",
                "gold_source_kind": "diamond_eval_holdout",
            },
            {
                "module": "Barrier",
                "module_path": "outputs/diamond_gen/synchronization_work/Barrier.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": False,
                "evidence_status": "reference_spec_only",
                "before_score": 0.9,
                "prompt_source_kind": None,
                "gold_source_kind": "public_seed_candidate",
            },
            {
                "module": "CopyingGc",
                "module_path": "outputs/diamond_gen/memory_caches_work/CopyingGc.tla",
                "repair_bucket": "inductiveness_repair",
                "repair_priority": "p2",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "before_score": 0.35,
                "prompt_source_kind": "formalllm_eval",
                "gold_source_kind": "formalllm_public_module",
            },
            {
                "module": "AlternatingBit",
                "module_path": "outputs/diamond_gen/networking_work/AlternatingBit.tla",
                "repair_bucket": "skip_harness_repair",
                "repair_priority": "p4",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "before_score": 0.05,
                "prompt_source_kind": "formalllm_eval",
                "gold_source_kind": "public_seed_candidate",
            },
        ],
    )
    _write_json(
        tmp_path / "failure_analysis.json",
        {
            "immediate_repair_rows": 5,
            "action_bucket_counts": {
                "proof_repair": 3,
                "inductiveness_repair": 1,
                "skip_harness_repair": 1,
                "skip_missing_contract": 270,
                "skip_sany_invalid": 191,
                "skip_other": 0,
            },
        },
    )

    worklist = build_worklist(
        repair_queue=tmp_path / "repair_queue.jsonl",
        repair_evidence=tmp_path / "repair_evidence.jsonl",
        failure_analysis=tmp_path / "failure_analysis.json",
        repo=tmp_path,
        top_n=2,
    )

    assert worklist["primary_focus"]["repair_bucket"] == "proof_repair"
    assert worklist["primary_focus"]["pair_ready_rows"] == 2
    assert worklist["primary_focus"]["top_modules"] == ["AtomicRegister", "Arp"]
    assert worklist["bucket_summary"]["proof_repair"] == {
        "evidence_status_counts": {
            "pair_ready": 2,
            "reference_spec_only": 1,
        },
        "pair_ready_rows": 2,
        "queue_rows": 3,
    }
    assert worklist["blocked_row_counts"] == {
        "skip_missing_contract": 270,
        "skip_other": 0,
        "skip_sany_invalid": 191,
    }
    assert worklist["top_targets_by_bucket"]["proof_repair"][0]["module"] == "AtomicRegister"
    assert worklist["top_targets_by_bucket"]["proof_repair"][0]["obligations_failed"] == 3
    assert worklist["top_targets_by_bucket"]["inductiveness_repair"][0]["module"] == "CopyingGc"
    assert worklist["top_targets_by_bucket"]["skip_harness_repair"][0]["module"] == "AlternatingBit"


def test_cli_writes_patch_worklist_json(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "repair_queue.jsonl",
        [
            {
                "module": "AtomicRegister",
                "module_path": "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "recommended_action": "collect_proof_repair_pair",
                "status": "tlaps_partial",
                "failure_excerpt": "[ERROR]: Could not prove or check:",
                "tlapm": {"obligations_failed": 3, "obligations_total": 10},
            }
        ],
    )
    _write_jsonl(
        tmp_path / "repair_evidence.jsonl",
        [
            {
                "module": "AtomicRegister",
                "module_path": "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "before_score": 0.7,
                "prompt_source_kind": "diamond_eval_holdout",
                "gold_source_kind": "diamond_eval_holdout",
            }
        ],
    )
    _write_json(
        tmp_path / "failure_analysis.json",
        {
            "immediate_repair_rows": 1,
            "action_bucket_counts": {
                "proof_repair": 1,
                "skip_missing_contract": 0,
                "skip_sany_invalid": 0,
                "skip_other": 0,
            },
        },
    )
    out = tmp_path / "patch_worklist.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repair-queue",
            str(tmp_path / "repair_queue.jsonl"),
            "--repair-evidence",
            str(tmp_path / "repair_evidence.jsonl"),
            "--failure-analysis",
            str(tmp_path / "failure_analysis.json"),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(result.stdout)
    assert payload["primary_focus"]["repair_bucket"] == "proof_repair"
    assert stdout["primary_focus"]["top_modules"] == ["AtomicRegister"]


def test_build_worklist_deduplicates_focus_module_names(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "repair_queue.jsonl",
        [
            {
                "module": "AsyncTerminationDetection",
                "module_path": "data/FormaLLM/data/ewd998/tla/AsyncTerminationDetection.tla",
                "repair_bucket": "tlc_repair",
                "repair_priority": "p3",
                "recommended_action": "collect_tlc_repair_pair",
                "status": "tlc_error",
                "failure_excerpt": "TLC produced no conclusive result:",
                "tlc_error_family": "tlc_error_no_conclusive_result",
            },
            {
                "module": "AsyncTerminationDetection",
                "module_path": "data/FormaLLM/data/ewd998/tla/AsyncTerminationDetection_clean.tla",
                "repair_bucket": "tlc_repair",
                "repair_priority": "p3",
                "recommended_action": "collect_tlc_repair_pair",
                "status": "tlc_error",
                "failure_excerpt": "TLC produced no conclusive result:",
                "tlc_error_family": "tlc_error_no_conclusive_result",
            },
        ],
    )
    _write_jsonl(
        tmp_path / "repair_evidence.jsonl",
        [
            {
                "module": "AsyncTerminationDetection",
                "module_path": "data/FormaLLM/data/ewd998/tla/AsyncTerminationDetection.tla",
                "repair_bucket": "tlc_repair",
                "repair_priority": "p3",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "before_score": 0.15,
                "prompt_source_kind": "formalllm_eval",
                "gold_source_kind": "formalllm_public_module",
            },
            {
                "module": "AsyncTerminationDetection",
                "module_path": "data/FormaLLM/data/ewd998/tla/AsyncTerminationDetection_clean.tla",
                "repair_bucket": "tlc_repair",
                "repair_priority": "p3",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "before_score": 0.15,
                "prompt_source_kind": "formalllm_eval",
                "gold_source_kind": "formalllm_public_module",
            },
        ],
    )
    _write_json(
        tmp_path / "failure_analysis.json",
        {
            "immediate_repair_rows": 2,
            "action_bucket_counts": {
                "proof_repair": 0,
                "inductiveness_repair": 0,
                "tlc_repair": 2,
                "skip_harness_repair": 0,
                "skip_missing_contract": 0,
                "skip_sany_invalid": 0,
                "skip_other": 0,
            },
        },
    )

    worklist = build_worklist(
        repair_queue=tmp_path / "repair_queue.jsonl",
        repair_evidence=tmp_path / "repair_evidence.jsonl",
        failure_analysis=tmp_path / "failure_analysis.json",
        repo=tmp_path,
        top_n=5,
    )

    assert worklist["primary_focus"]["top_modules"] == ["AsyncTerminationDetection"]
