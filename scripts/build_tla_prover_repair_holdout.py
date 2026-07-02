"""Build the held-out repair eval set and assert train/eval disjointness.

The repair-GRPO lane trains on every row of the proof_repair_primary corpus
(20 benchmark-derived + 15 validated pairs), so any evaluation of a repair
checkpoint on those rows is a coverage number, never generalization. This
script materializes the rows that are validated but NOT trained on as
`tla_prover_repair_eval_holdout_v1.jsonl`, and acts as the leakage gate the
memo/eval partition rule requires: it exits nonzero if the holdout is empty
or if any holdout row leaks into the training corpus.

Usage:
    python3 scripts/build_tla_prover_repair_holdout.py \
        [--train PATH] [--validated PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEFAULT_TRAIN = REPO / "data" / "processed" / "tla_prover_repair_train_proof_repair_primary_v1.jsonl"
DEFAULT_VALIDATED = REPO / "data" / "processed" / "tla_prover_full_dataset_validated_repair_pairs_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "tla_prover_repair_eval_holdout_v1.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_holdout(train_path: Path, validated_path: Path) -> tuple[list[dict], dict]:
    train_ids = {row["repair_id"] for row in _read_jsonl(train_path)}
    validated = _read_jsonl(validated_path)

    holdout = [row for row in validated if row["repair_id"] not in train_ids]
    holdout_ids = [row["repair_id"] for row in holdout]
    leaked = sorted({row["repair_id"] for row in holdout} & train_ids)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "train_source": str(train_path.name),
        "validated_source": str(validated_path.name),
        "train_rows": len(train_ids),
        "validated_rows": len(validated),
        "holdout_rows": len(holdout),
        "holdout_repair_ids": sorted(holdout_ids),
        "train_overlap": leaked,
        "ok": bool(holdout) and not leaked,
    }
    return holdout, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--validated", type=Path, default=DEFAULT_VALIDATED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    holdout, summary = build_holdout(args.train, args.validated)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in holdout),
        encoding="utf-8",
    )
    summary_path = args.out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({k: summary[k] for k in ("train_rows", "validated_rows", "holdout_rows", "train_overlap", "ok")}, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
