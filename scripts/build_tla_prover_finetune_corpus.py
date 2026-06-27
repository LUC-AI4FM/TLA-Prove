#!/usr/bin/env python3
"""Combine current ChatTLA SFT data with verified TLAPS proof examples."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_BASE = REPO / "data" / "processed" / "diamond_sft_v3.jsonl"
DEFAULT_VERIFIED = REPO / "data" / "processed" / "tla_prover" / "verified_tlaps_sft_seed.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "tla_prover" / "chattla_tla_prover_sft_v1.jsonl"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    assistant_indexes = [i for i, msg in enumerate(messages) if msg.get("role") == "assistant"]
    final_assistant = assistant_indexes[-1] if assistant_indexes else None

    for i, msg in enumerate(messages):
        item = dict(msg)
        if item.get("role") == "system":
            item["role"] = "developer"
        if item.get("role") == "assistant" and not item.get("channel"):
            item["channel"] = "final" if i == final_assistant else "analysis"
        normalized.append(item)
    return normalized


def _normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if isinstance(out.get("messages"), list):
        out["messages"] = normalize_messages(out["messages"])
    return out


def _verified_record(row: dict[str, Any]) -> dict[str, Any]:
    return _normalize_record({
        "_tier": "verified_tlaps_proof",
        "_source": "tlaps_reproduced_final_160816",
        "_module": row.get("module"),
        "_verifier": row.get("verifier"),
        "_source_artifact": row.get("source_artifact"),
        "messages": row["messages"],
    })


def build_corpus(
    base_path: Path,
    verified_path: Path,
    *,
    tlaps_weight: int,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_rows = [_normalize_record(row) for row in _load_jsonl(base_path)]
    verified_rows = [_verified_record(row) for row in _load_jsonl(verified_path)]

    combined = list(base_rows)
    for _ in range(tlaps_weight):
        combined.extend(dict(row) for row in verified_rows)

    random.Random(seed).shuffle(combined)
    summary = {
        "base": str(base_path),
        "verified_tlaps": str(verified_path),
        "base_rows": len(base_rows),
        "verified_tlaps_rows": len(verified_rows),
        "verified_tlaps_weight": tlaps_weight,
        "total_rows": len(combined),
        "seed": seed,
    }
    return combined, summary


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    final_summary = dict(summary)
    final_summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    final_summary["out"] = str(out)
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_summary["summary"] = str(summary_path)
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--verified", type=Path, default=DEFAULT_VERIFIED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--tlaps-weight", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260627)
    args = parser.parse_args()

    rows, summary = build_corpus(
        args.base,
        args.verified,
        tlaps_weight=args.tlaps_weight,
        seed=args.seed,
    )
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
