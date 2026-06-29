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
DEFAULT_FORMALLLM = REPO / "data" / "processed" / "formalllm_eval_v1.jsonl"
DEFAULT_VERIFIED = REPO / "data" / "processed" / "tla_prover" / "verified_tlaps_sft_seed.jsonl"
DEFAULT_PUBLIC_IMPORT = REPO / "data" / "processed" / "ai4fm_public_tlaprove_import_v1.jsonl"
DEFAULT_PUBLIC_SEED_CANDIDATES = REPO / "data" / "processed" / "ai4fm_public_seed_prover_candidates_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "tla_prover" / "chattla_tla_prover_sft_v1.jsonl"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


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


def _sanitize_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_public_value(item) for item in value]
    if isinstance(value, str) and value.startswith("/"):
        return Path(value).name
    return value


def _verified_record(row: dict[str, Any]) -> dict[str, Any]:
    return _normalize_record({
        "_tier": "verified_tlaps_proof",
        "_source": "tlaps_reproduced_final_160816",
        "_module": row.get("module"),
        "_verifier": row.get("verifier"),
        "_source_artifact": _sanitize_public_value(row.get("source_artifact")),
        "messages": row["messages"],
    })


def _public_seed_candidate_record(row: dict[str, Any]) -> dict[str, Any]:
    module = str(row.get("module") or "RecoveredModule")
    source_path = row.get("source_path")
    repo = row.get("repo")
    content = str(row.get("content") or "").strip()
    return _normalize_record(
        {
            "_tier": "public_seed_prover_candidate_replay",
            "_source": "ai4fm_public_seed_prover_candidates_v1",
            "_module": module,
            "_source_repo": repo,
            "_source_path": source_path,
            "messages": [
                {
                    "role": "developer",
                    "content": (
                        "You are ChatTLA, an expert at writing valid TLA+ modules and proofs. "
                        "Output only TLA+ code."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Produce the complete TLA+ module for {module}. "
                        "Preserve a valid module header, operators, and any proof obligations present."
                    ),
                },
                {
                    "role": "assistant",
                    "channel": "final",
                    "content": content,
                },
            ],
        }
    )


def build_corpus(
    base_path: Path,
    formalllm_path: Path,
    verified_path: Path,
    *,
    tlaps_weight: int,
    seed: int,
    public_import_path: Path | None = None,
    public_import_weight: int = 0,
    public_seed_candidates_path: Path | None = None,
    public_seed_candidates_weight: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_rows = [_normalize_record(row) for row in _load_jsonl(base_path)]
    formalllm_rows = [_normalize_record(row) for row in _load_jsonl(formalllm_path)]
    verified_rows = [_verified_record(row) for row in _load_jsonl(verified_path)]
    public_import_rows = (
        [_normalize_record(row) for row in _load_jsonl(public_import_path)]
        if public_import_path is not None and public_import_weight > 0
        else []
    )
    public_seed_candidate_rows = (
        [_public_seed_candidate_record(row) for row in _load_jsonl(public_seed_candidates_path)]
        if public_seed_candidates_path is not None and public_seed_candidates_weight > 0
        else []
    )

    combined = list(base_rows)
    combined.extend(formalllm_rows)
    for _ in range(tlaps_weight):
        combined.extend(dict(row) for row in verified_rows)
    for _ in range(public_import_weight):
        combined.extend(dict(row) for row in public_import_rows)
    for _ in range(public_seed_candidates_weight):
        combined.extend(dict(row) for row in public_seed_candidate_rows)

    random.Random(seed).shuffle(combined)
    summary = {
        "base": _display_path(base_path),
        "formalllm": _display_path(formalllm_path),
        "verified_tlaps": _display_path(verified_path),
        "base_rows": len(base_rows),
        "formalllm_rows": len(formalllm_rows),
        "verified_tlaps_rows": len(verified_rows),
        "verified_tlaps_weight": tlaps_weight,
        "public_import": _display_path(public_import_path) if public_import_path is not None else None,
        "public_import_rows": len(public_import_rows),
        "public_import_weight": public_import_weight,
        "public_seed_candidates": (
            _display_path(public_seed_candidates_path) if public_seed_candidates_path is not None else None
        ),
        "public_seed_candidates_rows": len(public_seed_candidate_rows),
        "public_seed_candidates_weight": public_seed_candidates_weight,
        "total_rows": len(combined),
        "seed": seed,
    }
    return combined, summary


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    final_summary = dict(summary)
    final_summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    final_summary["out"] = _display_path(out)
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_summary["summary"] = _display_path(summary_path)
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--formalllm", type=Path, default=DEFAULT_FORMALLLM)
    parser.add_argument("--verified", type=Path, default=DEFAULT_VERIFIED)
    parser.add_argument("--public-import", type=Path, default=DEFAULT_PUBLIC_IMPORT)
    parser.add_argument("--public-import-weight", type=int, default=0)
    parser.add_argument("--public-seed-candidates", type=Path, default=DEFAULT_PUBLIC_SEED_CANDIDATES)
    parser.add_argument("--public-seed-candidates-weight", type=int, default=0)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--tlaps-weight", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260627)
    args = parser.parse_args()

    rows, summary = build_corpus(
        args.base,
        args.formalllm,
        args.verified,
        tlaps_weight=args.tlaps_weight,
        seed=args.seed,
        public_import_path=args.public_import,
        public_import_weight=args.public_import_weight,
        public_seed_candidates_path=args.public_seed_candidates,
        public_seed_candidates_weight=args.public_seed_candidates_weight,
    )
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
