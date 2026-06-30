import json
import subprocess
import sys
from pathlib import Path

from scripts.build_tla_prover_patch_packets import build_packets


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_tla_prover_patch_packets.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def test_build_packets_surfaces_primary_focus_targets(tmp_path: Path) -> None:
    (tmp_path / "outputs/diamond_gen/communication_protocols_work").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outputs/diamond_gen/synchronization_work").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/FormaLLM/data/lamport_mutex/tla").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla").write_text(
        "---- MODULE AtomicRegister ----\nVARIABLE x\nInit == x = 0\n====\n",
        encoding="utf-8",
    )
    (tmp_path / "outputs/diamond_gen/communication_protocols_work/Arp.tla").write_text(
        "---- MODULE Arp ----\nVARIABLE cache\nInit == cache = {}\n====\n",
        encoding="utf-8",
    )
    (tmp_path / "outputs/diamond_gen/synchronization_work/Barrier.tla").write_text(
        "---- MODULE Barrier ----\nVARIABLE waiting\nInit == waiting = 0\n====\n",
        encoding="utf-8",
    )
    (tmp_path / "data/FormaLLM/data/lamport_mutex/tla/LamportMutex.tla").write_text(
        "---- MODULE LamportMutex ----\nVARIABLE owner\nInit == owner = 0\n====\n",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / "patch_worklist.json",
        {
            "primary_focus": {
                "repair_bucket": "proof_repair",
                "pair_ready_rows": 2,
                "queue_rows": 3,
                "top_modules": ["AtomicRegister", "Arp"],
                "reason": "highest priority",
            },
            "recommended_next_step": "Start with proof_repair.",
            "top_targets_by_bucket": {
                "proof_repair": [
                    {
                        "module": "AtomicRegister",
                        "module_path": "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla",
                        "repair_bucket": "proof_repair",
                    },
                    {
                        "module": "Arp",
                        "module_path": "outputs/diamond_gen/communication_protocols_work/Arp.tla",
                        "repair_bucket": "proof_repair",
                    },
                ],
                "tlc_repair": [
                    {
                        "module": "LamportMutex",
                        "module_path": "data/FormaLLM/data/lamport_mutex/tla/LamportMutex.tla",
                        "repair_bucket": "tlc_repair",
                    }
                ],
            },
        },
    )
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
                "runtime_seconds": 48.442,
                "target": "Spec => []TypeOK",
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
                "runtime_seconds": 36.439,
                "target": "Spec => []TypeOK",
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
                "runtime_seconds": 19.839,
                "target": "Spec => []TypeOK",
                "tlapm": {"obligations_failed": 1, "obligations_total": 10},
            },
            {
                "module": "LamportMutex",
                "module_path": "data/FormaLLM/data/lamport_mutex/tla/LamportMutex.tla",
                "repair_bucket": "tlc_repair",
                "repair_priority": "p3",
                "recommended_action": "collect_tlc_repair_pair",
                "status": "tlc_error",
                "failure_excerpt": "TLC produced no conclusive result:",
                "runtime_seconds": 9.5,
                "target": "Spec => []TypeOK",
                "tlapm": {},
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
                "prompt_source_path": "data/processed/diamond_eval_holdout.jsonl",
                "prompt_source_prompt_id": "atomic-register-broken",
                "gold_source_kind": "diamond_eval_holdout",
                "gold_source_path": "data/processed/diamond_eval_holdout.jsonl",
                "gold_source_repo": None,
                "broken_spec_path": "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla",
                "broken_spec_sha256": "broken-a",
                "repaired_spec": "---- MODULE AtomicRegister ----\nVARIABLE x\nInit == x \\in Nat\n====\n",
                "repaired_spec_sha256": "repaired-a",
                "repaired_spec_chars": 1200,
                "errors_rendered": "3/10 obligations failed",
                "nl": "atomic register prompt",
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
                "prompt_source_path": "data/processed/diamond_eval_holdout.jsonl",
                "prompt_source_prompt_id": "arp-broken",
                "gold_source_kind": "diamond_eval_holdout",
                "gold_source_path": "data/processed/diamond_eval_holdout.jsonl",
                "gold_source_repo": None,
                "broken_spec_path": "outputs/diamond_gen/communication_protocols_work/Arp.tla",
                "broken_spec_sha256": "broken-b",
                "repaired_spec": "---- MODULE Arp ----\nVARIABLE cache\nInit == cache \\in [Nat -> Nat]\n====\n",
                "repaired_spec_sha256": "repaired-b",
                "repaired_spec_chars": 900,
                "errors_rendered": "2/10 obligations failed",
                "nl": "arp prompt",
            },
            {
                "module": "Barrier",
                "module_path": "outputs/diamond_gen/synchronization_work/Barrier.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "before_score": 0.9,
                "prompt_source_kind": "diamond_eval_holdout",
                "prompt_source_path": "data/processed/diamond_eval_holdout.jsonl",
                "prompt_source_prompt_id": "barrier-broken",
                "gold_source_kind": "diamond_eval_holdout",
                "gold_source_path": "data/processed/diamond_eval_holdout.jsonl",
                "gold_source_repo": None,
                "broken_spec_path": "outputs/diamond_gen/synchronization_work/Barrier.tla",
                "broken_spec_sha256": "broken-barrier",
                "repaired_spec": "---- MODULE Barrier ----\nVARIABLE waiting\nInit == waiting \\in Nat\n====\n",
                "repaired_spec_sha256": "repaired-barrier",
                "repaired_spec_chars": 700,
                "errors_rendered": "1/10 obligations failed",
                "nl": "barrier prompt",
            },
            {
                "module": "LamportMutex",
                "module_path": "data/FormaLLM/data/lamport_mutex/tla/LamportMutex.tla",
                "repair_bucket": "tlc_repair",
                "repair_priority": "p3",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "before_score": 0.15,
                "prompt_source_kind": "formalllm_eval",
                "prompt_source_path": "data/processed/formalllm_eval_v1.jsonl",
                "prompt_source_prompt_id": "lamport-mutex-broken",
                "gold_source_kind": "formalllm_public_module",
                "gold_source_path": "data/FormaLLM/data/lamport_mutex/tla/LamportMutex_clean.tla",
                "gold_source_repo": "FormaLLM",
                "broken_spec_path": "data/FormaLLM/data/lamport_mutex/tla/LamportMutex.tla",
                "broken_spec_sha256": "broken-c",
                "repaired_spec": "---- MODULE LamportMutex ----\nVARIABLE owner\nInit == owner \\in Nat\n====\n",
                "repaired_spec_sha256": "repaired-c",
                "repaired_spec_chars": 800,
                "errors_rendered": "tlc timeout",
                "nl": "lamport mutex prompt",
            },
        ],
    )

    payload = build_packets(
        patch_worklist=tmp_path / "patch_worklist.json",
        repair_queue=tmp_path / "repair_queue.jsonl",
        repair_evidence=tmp_path / "repair_evidence.jsonl",
        repo=tmp_path,
    )

    assert payload["primary_focus"]["repair_bucket"] == "proof_repair"
    assert payload["primary_focus_packets"][0]["module"] == "AtomicRegister"
    assert payload["primary_focus_packets"][0]["obligations_failed"] == 3
    assert payload["primary_focus_packets"][0]["prompt_source_path"] == "data/processed/diamond_eval_holdout.jsonl"
    assert payload["primary_focus_packets"][0]["broken_spec"].startswith("---- MODULE AtomicRegister ----")
    assert payload["primary_focus_packets"][0]["repaired_spec"].startswith("---- MODULE AtomicRegister ----")
    assert "-Init == x = 0" in payload["primary_focus_packets"][0]["repair_diff"]
    assert "+Init == x \\in Nat" in payload["primary_focus_packets"][0]["repair_diff"]
    assert payload["primary_focus_packets"][0]["replay_command"] == (
        "python3 scripts/replay_tla_prover_full_dataset_subset.py "
        "--module-path outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla"
    )
    assert payload["primary_focus_packets"][1]["module"] == "Arp"
    assert payload["primary_focus_packets"][2]["module"] == "Barrier"
    assert payload["packets_by_bucket"]["tlc_repair"][0]["module"] == "LamportMutex"
    assert payload["packets_by_bucket"]["tlc_repair"][0]["gold_source_repo"] == "FormaLLM"
    assert payload["counts_by_bucket"] == {"proof_repair": 3, "tlc_repair": 1}


def test_cli_writes_patch_packet_manifest(tmp_path: Path) -> None:
    (tmp_path / "outputs/diamond_gen/communication_protocols_work").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla").write_text(
        "---- MODULE AtomicRegister ----\nVARIABLE x\nInit == x = 0\n====\n",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / "patch_worklist.json",
        {
            "primary_focus": {"repair_bucket": "proof_repair"},
            "recommended_next_step": "Start with proof_repair.",
            "top_targets_by_bucket": {
                "proof_repair": [
                    {
                        "module": "AtomicRegister",
                        "module_path": "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla",
                        "repair_bucket": "proof_repair",
                    }
                ]
            },
        },
    )
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
                "runtime_seconds": 48.442,
                "target": "Spec => []TypeOK",
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
                "prompt_source_path": "data/processed/diamond_eval_holdout.jsonl",
                "gold_source_kind": "diamond_eval_holdout",
                "gold_source_path": "data/processed/diamond_eval_holdout.jsonl",
                "broken_spec_path": "outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla",
                "broken_spec_sha256": "broken-a",
                "repaired_spec": "---- MODULE AtomicRegister ----\nVARIABLE x\nInit == x \\in Nat\n====\n",
                "repaired_spec_sha256": "repaired-a",
            }
        ],
    )
    out = tmp_path / "patch_packets.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--patch-worklist",
            str(tmp_path / "patch_worklist.json"),
            "--repair-queue",
            str(tmp_path / "repair_queue.jsonl"),
            "--repair-evidence",
            str(tmp_path / "repair_evidence.jsonl"),
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
    assert payload["primary_focus_packets"][0]["module"] == "AtomicRegister"
    assert payload["primary_focus_packets"][0]["repair_diff"]
    assert payload["primary_focus_packets"][0]["replay_command"].endswith(
        "--module-path outputs/diamond_gen/communication_protocols_work/AtomicRegister.tla"
    )
    assert stdout["counts_by_bucket"] == {"proof_repair": 1}
