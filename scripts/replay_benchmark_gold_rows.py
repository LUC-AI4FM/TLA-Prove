"""Re-verify the recorded TLC-gold rows of the newest full benchmark CSV.

The readiness manifests quote SANY/TLC counts from the benchmark CSV; this
script closes the loop by re-running the actual verifier on every row the CSV
records as TLC-gold, so the published number is backed by reproducible
evidence rather than a recorded flag. Writes a small manifest and exits
nonzero if any recorded gold fails to reproduce.

Usage:
    python3 scripts/replay_benchmark_gold_rows.py \
        [--csv PATH] [--out outputs/manifests/benchmark_gold_replay.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.training.publish_hf import default_benchmark_model  # noqa: E402
from src.validators.tlc_validator import validate_string  # noqa: E402

DEFAULT_OUT = REPO / "outputs" / "manifests" / "benchmark_gold_replay.json"
_MODULE_RE = re.compile(r"MODULE\s+(\w+)")


def newest_full_benchmark_csv(model: str | None) -> Path | None:
    pattern = "benchmark_results_*_full_*.csv"
    candidates = sorted(
        list((REPO / "outputs").glob(pattern))
        + list((REPO / "outputs" / "benchmark_results").glob(pattern)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue
        if model is None or any(r.get("model", "").strip() == model for r in rows):
            return path
    return None


def replay(csv_path: Path) -> dict:
    csv.field_size_limit(10_000_000)
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    golds = [r for r in rows if str(r.get("tlc_pass", "")).strip() in ("1", "True", "true")]
    results = []
    for row in golds:
        spec = row.get("generated_spec", "")
        m = _MODULE_RE.search(spec)
        verdict = validate_string(spec, module_name=m.group(1) if m else "Temp")
        results.append(
            {
                "benchmark_id": row.get("benchmark_id"),
                "recorded_tier": "gold",
                "replayed_tier": verdict.tier,
                "reproduced": verdict.tier == "gold",
                "sany_errors": verdict.sany_errors[:2],
            }
        )
    reproduced = sum(1 for r in results if r["reproduced"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(csv_path.relative_to(REPO)),
        "gold_rows": len(golds),
        "reproduced": reproduced,
        "ok": reproduced == len(golds),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=None,
                        help="Benchmark CSV to replay (default: newest full CSV for the default benchmark model)")
    parser.add_argument("--model", default=default_benchmark_model(),
                        help="Model tag used to pick the newest CSV when --csv is omitted")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    csv_path = args.csv or newest_full_benchmark_csv(args.model) or newest_full_benchmark_csv(None)
    if csv_path is None:
        print(json.dumps({"ok": False, "error": "no benchmark CSV found"}))
        return 2

    report = replay(csv_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("source_csv", "gold_rows", "reproduced", "ok")}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
