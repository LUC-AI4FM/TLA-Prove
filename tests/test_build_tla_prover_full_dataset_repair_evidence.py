import json
import subprocess
import sys
from pathlib import Path

from scripts.build_tla_prover_full_dataset_repair_evidence import build_evidence


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_tla_prover_full_dataset_repair_evidence.py"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_build_evidence_classifies_pair_ready_and_partial_matches(tmp_path: Path) -> None:
    broken_atomic = tmp_path / "broken" / "AtomicRegister.tla"
    broken_atomic.parent.mkdir(parents=True, exist_ok=True)
    broken_atomic.write_text("---- MODULE AtomicRegister ----\nVARIABLES x\n====\n", encoding="utf-8")
    broken_sync = tmp_path / "broken" / "SyncTerminationDetection.tla"
    broken_sync.write_text("---- MODULE SyncTerminationDetection ----\nVARIABLES x\n====\n", encoding="utf-8")
    broken_alt = tmp_path / "broken" / "AlternatingBit.tla"
    broken_alt.write_text("---- MODULE AlternatingBit ----\nVARIABLES x\n====\n", encoding="utf-8")
    broken_unknown = tmp_path / "broken" / "UnknownSpec.tla"
    broken_unknown.write_text("---- MODULE UnknownSpec ----\nVARIABLES x\n====\n", encoding="utf-8")

    queue = tmp_path / "repair_queue.jsonl"
    _write_jsonl(
        queue,
        [
            {
                "module": "AtomicRegister",
                "module_path": str(broken_atomic),
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "recommended_action": "collect_proof_repair_pair",
                "status": "tlaps_partial",
                "target": "Spec => []TypeOK",
                "failure_excerpt": "[ERROR]: Could not prove or check:",
                "tlapm": {"obligations_failed": 3, "obligations_proved": 7, "obligations_total": 10},
            },
            {
                "module": "SyncTerminationDetection",
                "module_path": str(broken_sync),
                "repair_bucket": "tlc_repair",
                "repair_priority": "p3",
                "recommended_action": "collect_tlc_repair_pair",
                "status": "tlc_error",
                "target": "Spec => []TypeOK",
                "failure_excerpt": "Attempted to enumerate Nat.",
                "tlc_error_family": "tlc_error_no_conclusive_result",
            },
            {
                "module": "AlternatingBit",
                "module_path": str(broken_alt),
                "repair_bucket": "skip_harness_repair",
                "repair_priority": "p4",
                "recommended_action": "patch_harness_and_replay",
                "status": "skipped",
                "target": "Spec => []TypeOK",
                "failure_excerpt": "missing variable domain",
                "skip_reason_family": "skip_missing_variable_domain",
            },
            {
                "module": "UnknownSpec",
                "module_path": str(broken_unknown),
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "recommended_action": "collect_proof_repair_pair",
                "status": "tlaps_partial",
                "target": "Spec => []TypeOK",
                "failure_excerpt": "[ERROR]: Could not prove or check:",
            },
        ],
    )

    diamond = tmp_path / "diamond_eval_holdout.jsonl"
    _write_jsonl(
        diamond,
        [
            {
                "module": "AtomicRegister",
                "topic_desc": "ABD-style register with majority quorums.",
                "spec": "---- MODULE AtomicRegister ----\nEXTENDS Naturals\n====\n",
                "tier": "gold",
            }
        ],
    )

    formalllm_eval = tmp_path / "formalllm_eval_v1.jsonl"
    _write_jsonl(
        formalllm_eval,
        [
            {
                "_module": "SyncTerminationDetection",
                "_prompt_id": "formalllm/ewd840/SyncTerminationDetection",
                "messages": [
                    {"role": "developer", "content": "ignored"},
                    {"role": "user", "content": "Write a TLA+ specification for synchronous termination detection."},
                    {"role": "assistant", "content": "ignored"},
                ],
            }
        ],
    )

    formalllm_public = tmp_path / "formalllm_public_tla_modules_v1.jsonl"
    _write_jsonl(
        formalllm_public,
        [
            {
                "module": "SyncTerminationDetection",
                "repo": "formalllm/public",
                "source_path": "data/FormaLLM/data/ewd840/tla/SyncTerminationDetection_clean.tla",
                "content": "---- MODULE SyncTerminationDetection ----\nEXTENDS Naturals\n====\n",
            }
        ],
    )

    public_seed = tmp_path / "ai4fm_public_seed_prover_candidates_v1.jsonl"
    _write_jsonl(
        public_seed,
        [
            {
                "module": "AlternatingBit",
                "repo": "tlaplus/Examples",
                "source_path": "specifications/AlternatingBit.tla",
                "content": "---- MODULE AlternatingBit ----\nEXTENDS Naturals\n====\n",
            }
        ],
    )

    rows, summary = build_evidence(
        repair_queue=queue,
        diamond_holdout=diamond,
        formalllm_eval=formalllm_eval,
        formalllm_public_modules=formalllm_public,
        public_seed_candidates=public_seed,
        repo=tmp_path,
    )

    by_module = {row["module"]: row for row in rows}
    assert by_module["AtomicRegister"]["evidence_status"] == "pair_ready"
    assert by_module["AtomicRegister"]["prompt_source_kind"] == "diamond_eval_holdout"
    assert by_module["AtomicRegister"]["gold_source_kind"] == "diamond_eval_holdout"
    assert by_module["AtomicRegister"]["nl"] == "ABD-style register with majority quorums."

    assert by_module["SyncTerminationDetection"]["evidence_status"] == "pair_ready"
    assert by_module["SyncTerminationDetection"]["prompt_source_kind"] == "formalllm_eval"
    assert by_module["SyncTerminationDetection"]["gold_source_kind"] == "formalllm_public_module"
    assert by_module["SyncTerminationDetection"]["gold_source_path"].endswith("SyncTerminationDetection_clean.tla")

    assert by_module["AlternatingBit"]["evidence_status"] == "reference_spec_only"
    assert by_module["AlternatingBit"]["gold_source_kind"] == "public_seed_candidate"
    assert by_module["AlternatingBit"]["pair_ready"] is False

    assert by_module["UnknownSpec"]["evidence_status"] == "no_evidence"
    assert by_module["UnknownSpec"]["pair_ready"] is False

    assert summary["rows"] == 4
    assert summary["pair_ready_rows"] == 2
    assert summary["evidence_status_counts"] == {
        "no_evidence": 1,
        "pair_ready": 2,
        "reference_spec_only": 1,
    }
    assert summary["bucket_pair_ready_counts"] == {
        "proof_repair": 1,
        "tlc_repair": 1,
    }


def test_cli_writes_full_dataset_repair_evidence(tmp_path: Path) -> None:
    broken = tmp_path / "broken" / "AtomicRegister.tla"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("---- MODULE AtomicRegister ----\nVARIABLES x\n====\n", encoding="utf-8")
    queue = tmp_path / "repair_queue.jsonl"
    _write_jsonl(
        queue,
        [
            {
                "module": "AtomicRegister",
                "module_path": str(broken),
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "recommended_action": "collect_proof_repair_pair",
                "status": "tlaps_partial",
                "target": "Spec => []TypeOK",
                "failure_excerpt": "[ERROR]: Could not prove or check:",
            }
        ],
    )
    diamond = tmp_path / "diamond_eval_holdout.jsonl"
    _write_jsonl(
        diamond,
        [
            {
                "module": "AtomicRegister",
                "topic_desc": "register prompt",
                "spec": "---- MODULE AtomicRegister ----\nEXTENDS Naturals\n====\n",
            }
        ],
    )
    formalllm_eval = tmp_path / "formalllm_eval_v1.jsonl"
    _write_jsonl(formalllm_eval, [])
    formalllm_public = tmp_path / "formalllm_public_tla_modules_v1.jsonl"
    _write_jsonl(formalllm_public, [])
    public_seed = tmp_path / "ai4fm_public_seed_prover_candidates_v1.jsonl"
    _write_jsonl(public_seed, [])
    out = tmp_path / "repair_evidence.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repair-queue",
            str(queue),
            "--diamond-holdout",
            str(diamond),
            "--formalllm-eval",
            str(formalllm_eval),
            "--formalllm-public-modules",
            str(formalllm_public),
            "--public-seed-candidates",
            str(public_seed),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["evidence_status"] == "pair_ready"
    summary = json.loads(out.with_suffix(".summary.json").read_text(encoding="utf-8"))
    assert summary["pair_ready_rows"] == 1
    stdout = json.loads(result.stdout)
    assert stdout["summary"]["rows"] == 1
