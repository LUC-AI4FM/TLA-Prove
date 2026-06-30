import json
import subprocess
from pathlib import Path

from scripts.choose_tla_prover_next_experiment import build_report, compact_report


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_build_report_prefers_repair_when_remote_decision_blocks_sft(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "patch",
            "full_dataset_verdict": "patch",
            "next_action": "Do not launch SFT. Patch prover harness/data first.",
        },
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        {
            "lanes": {
                "default": {
                    "path": "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
                    "rows": 1330,
                    "trainable": True,
                },
                "expanded": {
                    "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
                    "rows": 2503,
                    "trainable": True,
                },
                "full-public": {
                    "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl",
                    "rows": 2508,
                    "trainable": True,
                }
            },
            "public_ai4fm_scope": {
                "canonical_formalllm_rows": 205,
                "tracked_tlaprove_public_rows": 2350,
                "all_public_tlaprove_rows": 2757,
            },
            "repair_corpus_status": {
                "rows": 533,
                "health": {"ok": True, "warnings": []},
                "missing_sources": ["data/processed/ralph_repair_pairs.jsonl"],
                "sources": {
                    "benchmark_fc128best": {"rows_in_merged_corpus": 20},
                    "synthetic": {"rows_in_merged_corpus": 491},
                    "full_dataset_validated": {"rows_in_merged_corpus": 22, "candidate_rows": 37},
                },
                "comparisons": {"validated_rows_added_beyond_benchmark": 22},
            },
        },
    )
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        {"health": {"ok": False, "warnings": ["benchmark_only_repair_corpus"]}},
    )

    report = build_report(tmp_path)

    assert report["recommended_action"] == "repair"
    assert report["intent_allowed"] is True
    assert report["recommended_command"] == "python3 scripts/train_tla_prover_repair_local.py --refresh-corpus"
    assert report["handoff_status"]["state"] == "results_ready"
    assert report["handoff_prerequisite"] is None
    assert report["repair_corpus_health"]["ok"] is False
    assert report["repair_corpus_summary"]["rows"] is None
    assert report["corpus_expansion_status"]["recommended_sequence"] == ["default", "expanded", "full-public"]
    assert report["corpus_expansion_status"]["public_ai4fm_scope"]["all_public_tlaprove_rows"] == 2757
    assert report["repair_expansion_status"]["sources"]["full_dataset_validated"]["rows_in_merged_corpus"] == 22
    assert report["comparison_plan_commands"][0]["comparison_id"] == "default-vs-expanded-local"
    assert report["comparison_plan_commands"][1]["comparison_id"] == "expanded-vs-full-public-local"
    assert "--baseline default --candidate expanded --mode local" in report["comparison_plan_commands"][0]["command"]
    assert "--baseline expanded --candidate full-public --mode local" in report["comparison_plan_commands"][1]["command"]


def test_build_report_prefers_expanded_sft_lane_after_remote_advance(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "advance",
            "full_dataset_verdict": "advance",
            "next_action": "Launch the next SFT decision.",
        },
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        {
            "lanes": {
                "default": {
                    "path": "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
                    "rows": 1330,
                    "trainable": True,
                },
                "expanded": {
                    "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
                    "rows": 2503,
                    "trainable": True,
                },
                "full-public": {
                    "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl",
                    "rows": 2508,
                    "trainable": True,
                }
            },
            "repair_corpus_status": {
                "rows": 533,
                "health": {"ok": True, "warnings": []},
                "missing_sources": [],
                "sources": {
                    "benchmark_fc128best": {"rows_in_merged_corpus": 20},
                    "synthetic": {"rows_in_merged_corpus": 491},
                    "full_dataset_validated": {"rows_in_merged_corpus": 22},
                },
                "comparisons": {"validated_rows_added_beyond_benchmark": 22},
            },
        },
    )
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )

    report = build_report(tmp_path)

    assert report["recommended_action"] == "sft-preflight"
    assert report["preferred_sft_lane"] == "expanded"
    assert "--sft-corpus expanded --submit-sft-preflight" in report["recommended_command"]
    assert report["recommended_local_command"] == "python3 scripts/train_tla_prover_local.py --sft-corpus expanded"
    assert report["handoff_prerequisite"] is None
    assert report["preferred_sft_lane_summary"]["trainable"] is True
    assert report["corpus_expansion_status"]["recommended_sequence"] == ["default", "expanded", "full-public"]
    assert report["repair_expansion_status"]["comparisons"]["validated_rows_added_beyond_benchmark"] == 22
    assert report["comparison_plan_commands"][0]["comparison_id"] == "default-vs-expanded-local"


def test_build_report_prefers_publish_when_candidate_readiness_clears(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "advance",
            "full_dataset_verdict": "advance",
            "next_action": "Launch the next SFT decision.",
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": True},
    )

    report = build_report(tmp_path)

    assert report["recommended_action"] == "publish"
    assert "--benchmark-model chattla:20b-fc128best" in report["recommended_command"]
    assert report["handoff_prerequisite"] is None


def test_build_report_surfaces_repair_corpus_summary_fields(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "patch",
            "full_dataset_verdict": "patch",
            "next_action": "Do not launch SFT. Patch prover harness/data first.",
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        {
            "rows": 510,
            "kept_rows_by_source": {"synthetic": 491, "benchmark": 19},
            "missing_sources": ["data/processed/ralph_repair_pairs.jsonl"],
            "health": {"ok": True, "warnings": []},
        },
    )

    report = build_report(tmp_path)

    assert report["repair_corpus_summary"]["rows"] == 510
    assert report["repair_corpus_summary"]["kept_rows_by_source"] == {"synthetic": 491, "benchmark": 19}
    assert report["repair_corpus_summary"]["missing_sources"] == ["data/processed/ralph_repair_pairs.jsonl"]


def test_build_report_surfaces_repair_workflow_details(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "patch",
            "full_dataset_verdict": "patch",
            "next_action": "Do not launch SFT. Patch prover harness/data first.",
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        {
            "rows": 510,
            "kept_rows_by_source": {"synthetic": 491, "benchmark": 19},
            "missing_sources": ["data/processed/ralph_repair_pairs.jsonl"],
            "health": {"ok": True, "warnings": []},
        },
    )
    _write(
        tmp_path / "data/processed/benchmark_repair_pairs_fc128best.summary.json",
        {
            "rows": 19,
            "failed_rows_seen": 20,
            "gold_coverage": {"covered_failed_rows": 19, "missing_gold_benchmark_ids": ["BM020"]},
        },
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_full_dataset_failure_analysis.json",
        {
            "immediate_repair_rows": 149,
            "action_bucket_counts": {
                "proof_repair": 79,
                "inductiveness_repair": 21,
                "tlc_repair": 12,
                "skip_harness_repair": 37,
                "skip_missing_contract": 270,
                "skip_sany_invalid": 191,
                "skip_other": 0,
            },
            "action_bucket_samples": {
                "proof_repair": [{"module": "Arp"}],
                "inductiveness_repair": [{"module": "CopyingGc"}],
                "tlc_repair": [{"module": "DmaTransfer"}],
                "skip_harness_repair": [{"module": "AlternatingBit"}],
            },
        },
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_full_dataset_repair_queue.summary.json",
        {
            "rows": 149,
            "priority_counts": {"p1": 79, "p2": 21, "p3": 12, "p4": 37},
            "repair_bucket_counts": {
                "proof_repair": 79,
                "inductiveness_repair": 21,
                "tlc_repair": 12,
                "skip_harness_repair": 37,
            },
        },
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_full_dataset_repair_evidence.summary.json",
        {
            "rows": 149,
            "pair_ready_rows": 37,
            "evidence_status_counts": {"no_evidence": 108, "pair_ready": 37, "prompt_only": 1, "reference_spec_only": 3},
        },
    )
    _write(
        tmp_path / "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.summary.json",
        {
            "rows": 22,
            "candidate_rows": 37,
            "validated_tier_counts": {"gold": 18, "silver": 5, "bronze": 6},
            "kept_by_bucket": {"proof_repair": 15, "inductiveness_repair": 3, "tlc_repair": 4},
        },
    )

    report = build_report(tmp_path)

    assert report["recommended_action"] == "repair"
    assert report["recommended_local_command"] == (
        "python3 scripts/train_tla_prover_repair_local.py "
        "--preflight --refresh-corpus --runtime-import-timeout-s 10"
    )
    assert report["repair_workflow"]["refresh_command"].startswith(
        "python3 scripts/build_tla_prover_full_dataset_repair_queue.py"
    )
    assert report["repair_workflow"]["train_command"] == "python3 scripts/train_tla_prover_repair_local.py --refresh-corpus"
    assert report["repair_workflow"]["full_dataset_repair_queue_command"] == (
        "python3 scripts/build_tla_prover_full_dataset_repair_queue.py"
    )
    assert report["repair_workflow"]["full_dataset_repair_queue_summary"]["rows"] == 149
    assert report["repair_workflow"]["full_dataset_repair_evidence_command"] == (
        "python3 scripts/build_tla_prover_full_dataset_repair_evidence.py"
    )
    assert report["repair_workflow"]["full_dataset_repair_evidence_summary"]["pair_ready_rows"] == 37
    assert report["repair_workflow"]["full_dataset_validated_repair_pairs_command"] == (
        "python3 scripts/build_tla_prover_full_dataset_validated_repair_pairs.py "
        "--allowed-tier gold --allowed-tier silver"
    )
    assert report["repair_workflow"]["full_dataset_validated_repair_pairs_summary"]["rows"] == 22
    assert report["repair_workflow"]["benchmark_gold_coverage"] == {
        "failed_rows_seen": 20,
        "covered_failed_rows": 19,
        "missing_gold_benchmark_ids": ["BM020"],
    }
    assert report["repair_workflow"]["failure_priority"]["immediate_repair_rows"] == 149
    assert report["repair_workflow"]["failure_priority"]["top_action_buckets"][:3] == [
        {"bucket": "proof_repair", "count": 79},
        {"bucket": "skip_harness_repair", "count": 37},
        {"bucket": "inductiveness_repair", "count": 21},
    ]
    assert report["repair_workflow"]["failure_priority"]["representative_modules"] == {
        "proof_repair": ["Arp"],
        "inductiveness_repair": ["CopyingGc"],
        "tlc_repair": ["DmaTransfer"],
        "skip_harness_repair": ["AlternatingBit"],
    }


def test_build_report_distinguishes_proof_artifact_from_public_benchmark_claim(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "patch",
            "full_dataset_verdict": "patch",
            "next_action": "Do not launch SFT. Patch prover harness/data first.",
            "proof_artifact_revalidated": False,
            "final_proof_verify_present": False,
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.json",
        {
            "benchmark_model": "chattla:20b",
            "ready_to_publish": False,
            "benchmark": {"rows": 20, "sany": 0, "tlc": 0},
            "blockers": ["latest full benchmark has zero SANY and zero TLC passes; do not publish this model"],
        },
    )
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {
            "benchmark_model": "chattla:20b-fc128best",
            "ready_to_publish": False,
            "benchmark": {"rows": 20, "sany": 0, "tlc": 0},
            "blockers": ["latest full benchmark has zero SANY and zero TLC passes; do not publish this model"],
        },
    )
    _write(
        tmp_path / "outputs/autoprover/tlaps_verify_published_161016/summary.json",
        {
            "modules": 18,
            "raw_proved": 299,
            "raw_total": 299,
            "all_modules_proved": True,
            "matches_expected_summary": True,
        },
    )

    report = build_report(tmp_path)

    assert report["proof_artifact_status"]["supports_published_proof_claim"] is True
    assert report["proof_artifact_status"]["raw_proved"] == 299
    assert report["public_benchmark_correctness_status"]["supports_public_benchmark_100_percent_claim"] is False
    assert report["public_benchmark_correctness_status"]["best_available_model"] is None


def test_build_report_can_surface_supported_public_benchmark_claim(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "advance",
            "full_dataset_verdict": "advance",
            "next_action": "Launch the next SFT decision.",
            "proof_artifact_revalidated": True,
            "final_proof_verify_present": True,
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.json",
        {
            "benchmark_model": "chattla:20b",
            "ready_to_publish": True,
            "benchmark": {"rows": 20, "sany": 20, "tlc": 20},
            "blockers": [],
        },
    )
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {
            "benchmark_model": "chattla:20b-fc128best",
            "ready_to_publish": False,
            "benchmark": {"rows": 20, "sany": 0, "tlc": 0},
            "blockers": ["latest full benchmark has zero SANY and zero TLC passes; do not publish this model"],
        },
    )
    _write(
        tmp_path / "outputs/autoprover/tlaps_verify_published_161016/summary.json",
        {
            "modules": 18,
            "raw_proved": 299,
            "raw_total": 299,
            "all_modules_proved": True,
            "matches_expected_summary": True,
        },
    )

    report = build_report(tmp_path)

    assert report["public_benchmark_correctness_status"]["supports_public_benchmark_100_percent_claim"] is True
    assert report["public_benchmark_correctness_status"]["best_available_model"] == "chattla:20b"


def test_cli_can_write_checked_in_next_experiment_manifest(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "patch",
            "full_dataset_verdict": "patch",
            "next_action": "Do not launch SFT. Patch prover harness/data first.",
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )

    out = tmp_path / "outputs/manifests/tla_prover_next_experiment.json"
    script = Path(__file__).resolve().parents[1] / "scripts" / "choose_tla_prover_next_experiment.py"
    subprocess.run(
        [
            "python3",
            str(script),
            "--repo",
            str(tmp_path),
            "--out",
            str(out),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["recommended_action"] == "repair"
    assert payload["recommended_local_command"] == (
        "python3 scripts/train_tla_prover_repair_local.py "
        "--preflight --refresh-corpus --runtime-import-timeout-s 10"
    )


def test_build_report_omits_handoff_prerequisite_when_results_are_ready(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "advance",
            "full_dataset_verdict": "advance",
            "next_action": "Launch the next SFT decision.",
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_submission.json",
        {
            "ok": True,
            "known18_job_id": "170001.sophia-pbs-01",
        },
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_watch.json",
        {
            "status": "complete",
        },
    )

    report = build_report(tmp_path)

    assert report["handoff_status"]["state"] == "results_ready"
    assert report["handoff_prerequisite"] is None


def test_compact_report_surfaces_handoff_prerequisite_and_core_fields(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "patch",
            "full_dataset_verdict": "patch",
            "next_action": "Do not launch SFT. Patch prover harness/data first.",
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )
    _write(
        tmp_path / "data/processed/tla_prover_repair_train_v1.summary.json",
        {
            "rows": 533,
            "health": {"ok": True, "warnings": []},
        },
    )

    compact = compact_report(build_report(tmp_path))

    assert compact["recommended_action"] == "repair"
    assert compact["handoff_state"] == "results_ready"
    assert compact["handoff_prerequisite_action"] is None
    assert compact["handoff_prerequisite_command"] is None
    assert compact["local_repair_status_present"] is False
    assert compact["local_repair_status_command"] == (
        "python3 scripts/train_tla_prover_repair_local.py --preflight --dry-run "
        "--runtime-import-timeout-s 10 "
        "--out outputs/manifests/tla_prover_local_repair_plan.json"
    )
    assert compact["repair_rows"] == 533


def test_cli_compact_outputs_small_next_experiment_packet(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "patch",
            "full_dataset_verdict": "patch",
            "next_action": "Do not launch SFT. Patch prover harness/data first.",
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )

    script = Path(__file__).resolve().parents[1] / "scripts" / "choose_tla_prover_next_experiment.py"
    result = subprocess.run(
        [
            "python3",
            str(script),
            "--repo",
            str(tmp_path),
            "--compact",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["recommended_action"] == "repair"
    assert payload["handoff_prerequisite_action"] is None
    assert "repair_corpus_summary" not in payload


def test_build_report_surfaces_local_repair_status_from_manifest(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "patch",
            "full_dataset_verdict": "patch",
            "next_action": "Do not launch SFT. Patch prover harness/data first.",
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_local_repair_plan.json",
        {
            "schema": "chattla_tla_prover_local_repair_plan_v1",
            "generated_at": "2026-06-30T11:36:05.155392+00:00",
            "python_executable": "/tmp/local/.venv/bin/python",
            "bootstrap_recommendation": {
                "command": None,
                "reason": "selected_python_runtime_import_timeouts",
                "selected_python": "/tmp/local/.venv/bin/python",
            },
            "preflight_report": {
                "ok": False,
                "runtime_dependencies": {
                    "ok": False,
                    "missing": [
                        {"module": "datasets.Dataset", "error": "TimeoutExpired: import timed out after 2.0s"},
                        {"module": "peft.LoraConfig", "error": "TimeoutExpired: import timed out after 2.0s"},
                    ],
                },
            },
        },
    )

    report = build_report(tmp_path)

    assert report["local_repair_status"]["present"] is True
    assert report["local_repair_status"]["preflight_ok"] is False
    assert report["local_repair_status"]["local_runtime_ready"] is False
    assert report["local_repair_status"]["runtime_missing_modules"] == [
        "datasets.Dataset",
        "peft.LoraConfig",
    ]
    assert report["local_repair_status"]["bootstrap_recommendation"]["reason"] == (
        "selected_python_runtime_import_timeouts"
    )
    assert "selected_python" not in report["local_repair_status"]["bootstrap_recommendation"]
    assert "python_executable" not in report["local_repair_status"]
    assert report["local_repair_status_command"] == (
        "python3 scripts/train_tla_prover_repair_local.py --preflight --dry-run "
        "--runtime-import-timeout-s 10 "
        "--out outputs/manifests/tla_prover_local_repair_plan.json"
    )
    assert "Local repair preflight is currently not ready on this machine" in report["rationale"]
    assert "missing runtime imports: datasets.Dataset, peft.LoraConfig" in report["rationale"]


def test_compact_report_surfaces_local_repair_status_when_manifest_exists(tmp_path: Path) -> None:
    _write(
        tmp_path / "outputs/manifests/tla_prover_remote_decision.json",
        {
            "verdict": "patch",
            "full_dataset_verdict": "patch",
            "next_action": "Do not launch SFT. Patch prover harness/data first.",
        },
    )
    _write(tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json", {"lanes": {}})
    _write(tmp_path / "outputs/manifests/hf_publish_readiness.json", {"ready_to_publish": False})
    _write(
        tmp_path / "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        {"ready_to_publish": False},
    )
    _write(
        tmp_path / "outputs/manifests/tla_prover_local_repair_plan.json",
        {
            "schema": "chattla_tla_prover_local_repair_plan_v1",
            "preflight_report": {
                "ok": True,
                "runtime_dependencies": {"ok": True, "missing": []},
            },
        },
    )

    compact = compact_report(build_report(tmp_path))

    assert compact["local_repair_status_present"] is True
    assert compact["local_runtime_ready"] is True
    assert compact["local_runtime_missing_modules"] == []
