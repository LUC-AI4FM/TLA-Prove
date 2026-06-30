import json
from pathlib import Path

from scripts.choose_tla_prover_next_experiment import build_report


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
                "expanded": {
                    "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
                    "trainable": True,
                }
            }
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
    assert "build_benchmark_repair_pairs.py" in report["recommended_command"]
    assert "build_tla_prover_repair_corpus.py" in report["recommended_command"]
    assert "--preflight-only" in report["recommended_command"]
    assert "scripts.train_rl_repair" in report["recommended_command"]
    assert report["repair_corpus_health"]["ok"] is False
    assert report["repair_corpus_summary"]["rows"] is None


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
                "expanded": {
                    "path": "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
                    "trainable": True,
                }
            }
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
