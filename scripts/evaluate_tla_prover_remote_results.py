#!/usr/bin/env python3
"""Turn mirrored known-18 TLA prover evidence into the next-action decision."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_remote_decision.json"
GOOD_STATUSES = {"tlaps_proved", "tlaps_partial"}
BAD_STATUSES = {
    "tlaps_unproved",
    "tlaps_parse_error",
    "tlc_error",
    "not_inductive",
    "skeleton_emitted",
}


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _display_path(path: Path | None, repo: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def evaluate_known18_summary(summary: dict[str, Any]) -> dict[str, Any]:
    rows = _int(summary.get("rows"))
    statuses = dict(summary.get("statuses") or {})
    tlaps_checked = _int(summary.get("tlaps_checked"))
    good_rows = sum(_int(statuses.get(status)) for status in GOOD_STATUSES)
    bad_hits = {status: _int(statuses.get(status)) for status in BAD_STATUSES if _int(statuses.get(status))}
    unknown_hits = {
        status: _int(count)
        for status, count in statuses.items()
        if status not in GOOD_STATUSES and status not in BAD_STATUSES and _int(count)
    }

    known18_passed = rows >= 18 and tlaps_checked >= 18 and good_rows >= 18 and not bad_hits and not unknown_hits
    verdict = "advance" if known18_passed else "patch"
    if known18_passed:
        next_action = (
            "Run the full 610-row corrected smoke before SFT; keep SFT gated on a fresh "
            "full-dataset decision report and SFT preflight."
        )
    else:
        next_action = (
            "Do not launch SFT. Patch prover prompting/reward/data until all 18 known modules "
            "reach tlaps_proved or tlaps_partial with no parser/TLC/inductiveness regressions."
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "known18_passed": known18_passed,
        "next_action": next_action,
        "rows": rows,
        "tlaps_checked": tlaps_checked,
        "statuses": statuses,
        "good_rows": good_rows,
        "bad_statuses": bad_hits,
        "unknown_statuses": unknown_hits,
        "tlaps_total_obligations": _int(summary.get("tlaps_total_obligations")),
        "tlaps_proved_obligations": _int(summary.get("tlaps_proved_obligations")),
        "tlaps_failed_obligations": _int(summary.get("tlaps_failed_obligations")),
    }


def evaluate_final_proof_verify_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary:
        return {
            "present": False,
            "passed": False,
            "artifact_verdict": "missing",
            "modules": 0,
            "exit_0": 0,
            "raw_proved": 0,
            "raw_total": 0,
            "matches_expected_summary": None,
            "artifact_next_action": (
                "No mirrored published-artifact verify summary yet; use the known-18 gate for infrastructure "
                "health and rerun the stronger final-proof verify lane when you need a fresh 299/299 proof claim."
            ),
        }

    modules = _int(summary.get("modules"))
    exit_0 = _int(summary.get("exit_0"))
    raw_proved = _int(summary.get("raw_proved"))
    raw_total = _int(summary.get("raw_total"))
    matches_expected_summary = summary.get("matches_expected_summary")
    passed = (
        modules >= 18
        and exit_0 >= 18
        and raw_total > 0
        and raw_proved == raw_total
        and bool(summary.get("all_modules_exit_0"))
        and bool(summary.get("all_modules_proved"))
        and matches_expected_summary is not False
    )
    artifact_verdict = "revalidated" if passed else "investigate"
    artifact_next_action = (
        "Published proof artifact revalidated; use this lane as the stronger remote regression gate for the 100% proof claim."
        if passed
        else "Published-artifact verify lane did not reproduce the expected proof result; inspect the final-proof verify summary/log before trusting the 100% claim."
    )
    return {
        "present": True,
        "passed": passed,
        "artifact_verdict": artifact_verdict,
        "modules": modules,
        "exit_0": exit_0,
        "raw_proved": raw_proved,
        "raw_total": raw_total,
        "matches_expected_summary": matches_expected_summary,
        "artifact_next_action": artifact_next_action,
    }


def evaluate_full_dataset_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary:
        return {
            "present": False,
            "rows": 0,
            "statuses": {},
            "training_evidence_rows": 0,
            "error_rows": 0,
            "full_dataset_verdict": "missing",
            "full_dataset_next_action": (
                "No mirrored full-dataset smoke summary yet; wait for the 610-row run to finish and mirror its summary before making an SFT decision."
            ),
        }

    statuses = dict(summary.get("statuses") or {})
    rows = _int(summary.get("rows"))
    training_evidence_rows = _int(statuses.get("tlaps_proved")) + _int(statuses.get("tlaps_partial"))
    error_rows = (
        _int(statuses.get("tlc_error"))
        + _int(statuses.get("tlaps_parse_error"))
        + _int(statuses.get("tlaps_unproved"))
        + _int(statuses.get("not_inductive"))
    )
    if rows < 610:
        verdict = "incomplete"
        next_action = (
            "Full-dataset smoke summary is present but incomplete; do not launch SFT until the full 610-row run is mirrored and re-evaluated."
        )
    elif error_rows > 0:
        verdict = "patch"
        next_action = (
            "Do not launch SFT. Patch prover harness/data to reduce TLC, TLAPS parse, TLAPS unproved, and non-inductive failures before using the 610-row smoke as a training gate."
        )
    else:
        verdict = "advance"
        next_action = (
            "Full 610-row smoke is clean enough to justify the next SFT decision; review the mirrored artifacts and launch only if the data mix still matches the intended training target."
        )
    return {
        "present": True,
        "rows": rows,
        "statuses": statuses,
        "training_evidence_rows": training_evidence_rows,
        "error_rows": error_rows,
        "full_dataset_verdict": verdict,
        "full_dataset_next_action": next_action,
    }


def discover_latest_summary(repo: Path = REPO) -> Path:
    candidates = sorted(
        (repo / "outputs" / "autoprover").glob("known18_corrected_smoke_*.summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("no outputs/autoprover/known18_corrected_smoke_*.summary.json found")
    return candidates[0]


def discover_latest_final_proof_verify_summary(repo: Path = REPO) -> Path:
    candidates = sorted(
        (repo / "outputs" / "autoprover").glob("tlaps_verify_published_*/summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("no outputs/autoprover/tlaps_verify_published_*/summary.json found")
    return candidates[0]


def discover_latest_full_dataset_summary(repo: Path = REPO) -> Path:
    candidates = sorted(
        (repo / "outputs" / "autoprover").glob("full_dataset_smoke_*.summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("no outputs/autoprover/full_dataset_smoke_*.summary.json found")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--summary", type=Path, help="Known-18 corrected smoke summary JSON")
    parser.add_argument(
        "--final-proof-verify-summary",
        type=Path,
        help="Published-artifact final-proof verify summary JSON",
    )
    parser.add_argument(
        "--full-dataset-summary",
        type=Path,
        help="Full 610-row corrected smoke summary JSON",
    )
    parser.add_argument(
        "--no-auto-discover-extra-lanes",
        action="store_true",
        help="Only use explicitly supplied final-proof/full-dataset paths; do not auto-discover them from the repo.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    repo = args.repo.resolve()

    summary_path = args.summary or discover_latest_summary(repo)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    decision = evaluate_known18_summary(summary)
    decision["summary_path"] = _display_path(summary_path, repo)
    final_summary_path = args.final_proof_verify_summary
    final_summary = None
    if final_summary_path is None and not args.no_auto_discover_extra_lanes:
        try:
            final_summary_path = discover_latest_final_proof_verify_summary(repo)
        except FileNotFoundError:
            final_summary_path = None
    if final_summary_path is not None:
        final_summary = json.loads(final_summary_path.read_text(encoding="utf-8"))
    artifact = evaluate_final_proof_verify_summary(final_summary)
    decision["final_proof_verify_summary_path"] = _display_path(final_summary_path, repo)
    decision["final_proof_verify_present"] = artifact["present"]
    decision["final_proof_verify_passed"] = artifact["passed"]
    decision["proof_artifact_revalidated"] = artifact["passed"]
    decision["artifact_verdict"] = artifact["artifact_verdict"]
    decision["artifact_next_action"] = artifact["artifact_next_action"]
    decision["final_proof_verify_modules"] = artifact["modules"]
    decision["final_proof_verify_exit_0"] = artifact["exit_0"]
    decision["final_proof_verify_raw_proved"] = artifact["raw_proved"]
    decision["final_proof_verify_raw_total"] = artifact["raw_total"]
    decision["final_proof_verify_matches_expected_summary"] = artifact["matches_expected_summary"]
    if artifact["passed"]:
        decision["next_action"] = f"{decision['next_action']} {artifact['artifact_next_action']}"
    full_dataset_summary_path = args.full_dataset_summary
    full_dataset_summary = None
    if full_dataset_summary_path is None and not args.no_auto_discover_extra_lanes:
        try:
            full_dataset_summary_path = discover_latest_full_dataset_summary(repo)
        except FileNotFoundError:
            full_dataset_summary_path = None
    if full_dataset_summary_path is not None:
        full_dataset_summary = json.loads(full_dataset_summary_path.read_text(encoding="utf-8"))
    full_dataset = evaluate_full_dataset_summary(full_dataset_summary)
    decision["full_dataset_summary_path"] = _display_path(full_dataset_summary_path, repo)
    decision["full_dataset_present"] = full_dataset["present"]
    decision["full_dataset_rows"] = full_dataset["rows"]
    decision["full_dataset_statuses"] = full_dataset["statuses"]
    decision["full_dataset_training_evidence_rows"] = full_dataset["training_evidence_rows"]
    decision["full_dataset_error_rows"] = full_dataset["error_rows"]
    decision["full_dataset_verdict"] = full_dataset["full_dataset_verdict"]
    decision["full_dataset_next_action"] = full_dataset["full_dataset_next_action"]
    if full_dataset["present"] and full_dataset["full_dataset_verdict"] != "advance":
        decision["verdict"] = "patch"
        decision["next_action"] = full_dataset["full_dataset_next_action"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
