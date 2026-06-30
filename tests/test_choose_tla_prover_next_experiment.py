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
    assert "scripts.train_rl_repair" in report["recommended_command"]
    assert report["repair_corpus_health"]["ok"] is False


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
