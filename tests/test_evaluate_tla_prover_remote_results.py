import json
import subprocess
from pathlib import Path

from scripts.evaluate_tla_prover_remote_results import (
    evaluate_final_proof_verify_summary,
    evaluate_full_dataset_summary,
    evaluate_known18_summary,
)


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "evaluate_tla_prover_remote_results.py"


def test_evaluator_recommends_advance_for_all_known18_proved() -> None:
    summary = {
        "rows": 18,
        "statuses": {"tlaps_proved": 18},
        "tlaps_checked": 18,
        "tlaps_total_obligations": 180,
        "tlaps_proved_obligations": 180,
        "tlaps_failed_obligations": 0,
    }

    result = evaluate_known18_summary(summary)

    assert result["verdict"] == "advance"
    assert result["known18_passed"] is True
    assert "full 610-row" in result["next_action"]


def test_evaluator_recommends_patch_when_no_tlaps_success() -> None:
    summary = {
        "rows": 18,
        "statuses": {"tlaps_unproved": 18},
        "tlaps_checked": 18,
        "tlaps_total_obligations": 180,
        "tlaps_proved_obligations": 90,
        "tlaps_failed_obligations": 90,
    }

    result = evaluate_known18_summary(summary)

    assert result["verdict"] == "patch"
    assert result["known18_passed"] is False
    assert "Do not launch SFT" in result["next_action"]


def test_evaluator_cli_writes_decision_report(tmp_path: Path) -> None:
    summary_path = tmp_path / "known18.summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "rows": 18,
                "statuses": {"tlaps_partial": 18},
                "tlaps_checked": 18,
                "tlaps_total_obligations": 180,
                "tlaps_proved_obligations": 150,
                "tlaps_failed_obligations": 30,
            }
        ),
        encoding="utf-8",
    )
    full_dataset_path = tmp_path / "full.summary.json"
    full_dataset_path.write_text(
        json.dumps(
            {
                "job": "170004",
                "rows": 610,
                "statuses": {
                    "skipped": 587,
                    "tlaps_partial": 23,
                },
                "tlaps_proved": 0,
                "tlaps_partial": 23,
                "tlaps_unproved": 0,
                "tlaps_parse_error": 0,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "decision.json"

    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--summary",
            str(summary_path),
            "--full-dataset-summary",
            str(full_dataset_path),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["verdict"] == "advance"
    assert payload["known18_passed"] is True


def test_final_proof_verify_evaluator_detects_revalidated_artifact() -> None:
    summary = {
        "modules": 18,
        "exit_0": 18,
        "raw_proved": 299,
        "raw_total": 299,
        "all_modules_exit_0": True,
        "all_modules_proved": True,
        "matches_expected_summary": True,
    }

    result = evaluate_final_proof_verify_summary(summary)

    assert result["present"] is True
    assert result["passed"] is True
    assert result["artifact_verdict"] == "revalidated"


def test_evaluator_cli_records_final_proof_verify_when_supplied(tmp_path: Path) -> None:
    known18_path = tmp_path / "known18.summary.json"
    known18_path.write_text(
        json.dumps(
            {
                "rows": 18,
                "statuses": {"tlaps_partial": 18},
                "tlaps_checked": 18,
                "tlaps_total_obligations": 180,
                "tlaps_proved_obligations": 150,
                "tlaps_failed_obligations": 30,
            }
        ),
        encoding="utf-8",
    )
    final_verify_path = tmp_path / "final.summary.json"
    final_verify_path.write_text(
        json.dumps(
            {
                "modules": 18,
                "exit_0": 18,
                "raw_proved": 299,
                "raw_total": 299,
                "all_modules_exit_0": True,
                "all_modules_proved": True,
                "matches_expected_summary": True,
            }
        ),
        encoding="utf-8",
    )
    full_dataset_path = tmp_path / "full.summary.json"
    full_dataset_path.write_text(
        json.dumps(
            {
                "job": "170004",
                "rows": 610,
                "statuses": {
                    "skipped": 587,
                    "tlaps_partial": 23,
                },
                "tlaps_proved": 0,
                "tlaps_partial": 23,
                "tlaps_unproved": 0,
                "tlaps_parse_error": 0,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "decision.json"

    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--summary",
            str(known18_path),
            "--final-proof-verify-summary",
            str(final_verify_path),
            "--full-dataset-summary",
            str(full_dataset_path),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["verdict"] == "advance"
    assert payload["known18_passed"] is True
    assert payload["proof_artifact_revalidated"] is True
    assert payload["artifact_verdict"] == "revalidated"
    assert payload["final_proof_verify_summary_path"] == str(final_verify_path)


def test_full_dataset_evaluator_records_status_mix_when_present() -> None:
    summary = {
        "job": "170004",
        "rows": 610,
        "statuses": {
            "skipped": 471,
            "tlaps_partial": 23,
            "tlaps_unproved": 2,
            "tlaps_parse_error": 2,
            "not_inductive": 17,
            "tlc_error": 95,
        },
        "tlaps_proved": 0,
        "tlaps_partial": 23,
        "tlaps_unproved": 2,
        "tlaps_parse_error": 2,
    }

    result = evaluate_full_dataset_summary(summary)

    assert result["present"] is True
    assert result["rows"] == 610
    assert result["training_evidence_rows"] == 23
    assert result["error_rows"] == 116
    assert result["full_dataset_verdict"] == "patch"
    assert "Do not launch SFT" in result["full_dataset_next_action"]


def test_evaluator_cli_records_full_dataset_summary_when_supplied(tmp_path: Path) -> None:
    known18_path = tmp_path / "known18.summary.json"
    known18_path.write_text(
        json.dumps(
            {
                "rows": 18,
                "statuses": {"tlaps_partial": 18},
                "tlaps_checked": 18,
                "tlaps_total_obligations": 180,
                "tlaps_proved_obligations": 150,
                "tlaps_failed_obligations": 30,
            }
        ),
        encoding="utf-8",
    )
    full_dataset_path = tmp_path / "full.summary.json"
    full_dataset_path.write_text(
        json.dumps(
            {
                "job": "170004",
                "rows": 610,
                "statuses": {
                    "skipped": 471,
                    "tlaps_partial": 23,
                    "tlaps_unproved": 2,
                    "tlaps_parse_error": 2,
                    "not_inductive": 17,
                    "tlc_error": 95,
                },
                "tlaps_proved": 0,
                "tlaps_partial": 23,
                "tlaps_unproved": 2,
                "tlaps_parse_error": 2,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "decision.json"

    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--summary",
            str(known18_path),
            "--full-dataset-summary",
            str(full_dataset_path),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["full_dataset_summary_path"] == str(full_dataset_path)
    assert payload["full_dataset_present"] is True
    assert payload["full_dataset_verdict"] == "patch"
    assert payload["verdict"] == "patch"
    assert "Do not launch SFT" in payload["next_action"]
    assert payload["full_dataset_training_evidence_rows"] == 23
    assert payload["full_dataset_error_rows"] == 116


def test_evaluator_cli_sanitizes_repo_relative_summary_paths(tmp_path: Path) -> None:
    repo_like = tmp_path / "repo"
    autoprover = repo_like / "outputs" / "autoprover"
    autoprover.mkdir(parents=True, exist_ok=True)
    known18_path = autoprover / "known18_corrected_smoke_170001.summary.json"
    known18_path.write_text(
        json.dumps(
            {
                "rows": 18,
                "statuses": {"tlaps_partial": 18},
                "tlaps_checked": 18,
                "tlaps_total_obligations": 180,
                "tlaps_proved_obligations": 150,
                "tlaps_failed_obligations": 30,
            }
        ),
        encoding="utf-8",
    )
    full_dataset_path = autoprover / "full_dataset_smoke_170004.summary.json"
    full_dataset_path.write_text(
        json.dumps(
            {
                "job": "170004",
                "rows": 610,
                "statuses": {
                    "skipped": 498,
                    "tlaps_partial": 79,
                    "not_inductive": 21,
                    "tlc_error": 12,
                },
                "tlaps_proved": 0,
                "tlaps_partial": 79,
                "tlaps_unproved": 0,
                "tlaps_parse_error": 0,
            }
        ),
        encoding="utf-8",
    )
    out = repo_like / "outputs" / "manifests" / "decision.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--repo",
            str(repo_like),
            "--summary",
            str(known18_path.relative_to(repo_like)),
            "--full-dataset-summary",
            str(full_dataset_path.relative_to(repo_like)),
            "--out",
            str(out.relative_to(repo_like)),
        ],
        cwd=repo_like,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary_path"] == "outputs/autoprover/known18_corrected_smoke_170001.summary.json"
    assert payload["full_dataset_summary_path"] == "outputs/autoprover/full_dataset_smoke_170004.summary.json"
