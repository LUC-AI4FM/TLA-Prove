import json
import subprocess
from pathlib import Path

from scripts.compare_tla_prover_eval_results import compare_eval_results


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "compare_tla_prover_eval_results.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_compare_cli_writes_eligible_report_and_summary(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    out = tmp_path / "report.json"
    _write_json(
        baseline,
        {
            "label": "baseline-run",
            "n": 10,
            "sany_pass": 6,
            "depth1_pass": 4,
            "tlc_pass": 3,
            "mean_reward": 0.5,
            "module_match": 7,
            "syntax_issue_rows": 2,
            "syntax_issue_count": 4,
        },
    )
    _write_json(
        candidate,
        {
            "label": "candidate-run",
            "n": 10,
            "sany_pass": 6,
            "depth1_pass": 5,
            "tlc_pass": 4,
            "mean_reward": 0.65,
            "module_match": 7,
            "syntax_issue_rows": 1,
            "syntax_issue_count": 2,
        },
    )

    completed = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == "chattla.tla_prover_eval_comparison.v1"
    assert payload["baseline_path"] == str(baseline)
    assert payload["candidate_path"] == str(candidate)
    assert payload["baseline"]["label"] == "baseline-run"
    assert payload["candidate"]["label"] == "candidate-run"
    assert payload["deltas"]["depth1_pass"] == 1
    assert payload["deltas"]["tlc_pass"] == 1
    assert payload["deltas"]["mean_reward"] == 0.15
    assert payload["checks"]["same_n"] is True
    assert payload["checks"]["reward_no_regression"] is True
    assert payload["checks"]["syntax_issue_rows_no_regression"] is True
    assert payload["improves_any"] is True
    assert payload["eligible"] is True
    assert "eligible=True" in completed.stdout
    assert "depth1 +1" in completed.stdout


def test_compare_eval_results_flags_regression_and_blocks_eligibility(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    _write_json(
        baseline,
        {
            "label": "base",
            "n": 8,
            "sany_pass": 5,
            "depth1_pass": 4,
            "tlc_pass": 4,
            "mean_reward": 0.7,
            "module_match": 6,
            "syntax_issue_rows": 1,
            "syntax_issue_count": 2,
        },
    )
    _write_json(
        candidate,
        {
            "label": "cand",
            "n": 8,
            "sany_pass": 6,
            "depth1_pass": 4,
            "tlc_pass": 3,
            "mean_reward": 0.71,
            "module_match": 6,
            "syntax_issue_rows": 1,
            "syntax_issue_count": 2,
        },
    )

    payload = compare_eval_results(baseline, candidate)

    assert payload["checks"]["same_n"] is True
    assert payload["checks"]["sany_no_regression"] is True
    assert payload["checks"]["tlc_no_regression"] is False
    assert payload["improves_any"] is True
    assert payload["eligible"] is False
    assert "tlc_no_regression" in payload["failed_checks"]


def test_compare_eval_results_defaults_sparse_fields_and_derives_labels(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline_sparse.json"
    candidate = tmp_path / "candidate_sparse.json"
    _write_json(
        baseline,
        {
            "n": 3,
            "sany_pass": 1,
        },
    )
    _write_json(
        candidate,
        {
            "n": 3,
            "sany_pass": 1,
        },
    )

    payload = compare_eval_results(baseline, candidate)

    assert payload["baseline"]["label"] == "baseline_sparse"
    assert payload["candidate"]["label"] == "candidate_sparse"
    assert payload["baseline"]["depth1_pass"] == 0
    assert payload["baseline"]["tlc_pass"] == 0
    assert payload["baseline"]["mean_reward"] == 0.0
    assert payload["baseline"]["module_match"] == 0
    assert payload["baseline"]["syntax_issue_rows"] == 0
    assert payload["baseline"]["syntax_issue_count"] == 0
    assert payload["checks"]["same_n"] is True
    assert payload["checks"]["module_match_no_regression"] is True
    assert payload["checks"]["syntax_issue_count_no_regression"] is True
    assert payload["improves_any"] is False
    assert payload["eligible"] is False
