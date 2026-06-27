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


def discover_latest_summary(repo: Path = REPO) -> Path:
    candidates = sorted(
        (repo / "outputs" / "autoprover").glob("known18_corrected_smoke_*.summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("no outputs/autoprover/known18_corrected_smoke_*.summary.json found")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, help="Known-18 corrected smoke summary JSON")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    summary_path = args.summary or discover_latest_summary()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    decision = evaluate_known18_summary(summary)
    decision["summary_path"] = str(summary_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
