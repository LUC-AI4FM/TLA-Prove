#!/usr/bin/env python3
"""Build the held-out TLAPS prover eval set from verified proof traces."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO / "data" / "processed" / "tla_prover" / "tlaps_verified_autoprover_traces_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "prover_eval.jsonl"

THEOREM_RE = re.compile(r"^(THEOREM|LEMMA|COROLLARY)\b")
PROOF_START_RE = re.compile(r"^\s*(PROOF\b|<\d+>|BY\b|OBVIOUS\b)")
END_MODULE_RE = re.compile(r"^={4,}\s*$")

DEVELOPER_PROMPT = """You are ChatTLA-Prover, an expert at writing TLAPS proofs for TLA+ theorems.
You will be given a TLA+ module containing definitions and a final theorem statement.
Write only the TLAPS proof body for that theorem. Do not repeat the theorem line.
Use TLAPS syntax and keep the proof checkable by tlapm.
Reasoning: low"""


@dataclass(frozen=True)
class TheoremSplit:
    preamble: str
    statement: str
    proof: str


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _top_level_theorem_starts(lines: list[str]) -> list[int]:
    return [idx for idx, line in enumerate(lines) if THEOREM_RE.match(line)]


def _block_end(lines: list[str], start: int) -> int:
    for idx in range(start + 1, len(lines)):
        if THEOREM_RE.match(lines[idx]) or END_MODULE_RE.match(lines[idx]):
            return idx
    return len(lines)


def _proof_start(block: list[str]) -> int:
    for idx, line in enumerate(block[1:], start=1):
        if PROOF_START_RE.match(line):
            return idx
    raise ValueError("final theorem has no proof body")


def split_final_theorem(proof_module: str) -> TheoremSplit:
    """Split a verified module into preamble, final theorem statement, and proof."""
    lines = proof_module.splitlines()
    starts = _top_level_theorem_starts(lines)
    if not starts:
        raise ValueError("proof module has no top-level theorem")

    theorem_start = starts[-1]
    theorem_end = _block_end(lines, theorem_start)
    block = lines[theorem_start:theorem_end]
    proof_start = _proof_start(block)

    preamble = "\n".join(lines[:theorem_start]).rstrip()
    statement = "\n".join(block[:proof_start]).strip()
    proof = "\n".join(block[proof_start:]).strip()
    if not preamble or not statement or not proof:
        raise ValueError("incomplete theorem split")
    return TheoremSplit(preamble=preamble, statement=statement, proof=proof)


def _messages(module: str, split: TheoremSplit) -> list[dict[str, str]]:
    user_content = (
        "Write the TLAPS proof for the final theorem in the following module.\n\n"
        f"Module: {module}\n\n"
        "```tla\n"
        f"{split.preamble}\n\n{split.statement}\n"
        "```"
    )
    return [
        {"role": "developer", "content": DEVELOPER_PROMPT},
        {"role": "user", "content": user_content},
        {"role": "assistant", "channel": "final", "content": split.proof},
    ]


def _record(row: dict[str, Any]) -> dict[str, Any]:
    module = str(row["module"])
    split = split_final_theorem(str(row["proof_module"]))
    tlaps = row.get("tlaps") or {}
    return {
        "_tier": "verified_tlaps_eval",
        "_source": "tlaps_verified_autoprover_traces_v1",
        "_module": module,
        "_target_theorem": row.get("target_theorem"),
        "_source_artifact": row.get("source"),
        "_verifier": row.get("verifier"),
        "_obligations_proved": tlaps.get("proved"),
        "_obligations_total": tlaps.get("total"),
        "_tlaps_exit_code": tlaps.get("exit_code"),
        "messages": _messages(module, split),
    }


def build_rows(source: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _load_jsonl(source)
    rows: list[dict[str, Any]] = []
    skipped_unverified = 0
    skipped_invalid = 0
    invalid_modules: list[str] = []

    for row in sorted(source_rows, key=lambda item: item.get("module", "")):
        module = str(row.get("module") or "")
        tlaps = row.get("tlaps") or {}
        if row.get("verified") is not True or tlaps.get("exit_code") != 0 or tlaps.get("failed") not in (0, None):
            skipped_unverified += 1
            continue
        try:
            rows.append(_record(row))
        except (KeyError, ValueError):
            skipped_invalid += 1
            invalid_modules.append(module or "<unknown>")

    summary = {
        "source": str(source),
        "source_rows": len(source_rows),
        "kept_rows": len(rows),
        "skipped_unverified": skipped_unverified,
        "skipped_invalid": skipped_invalid,
        "invalid_modules": invalid_modules,
        "modules": [row["_module"] for row in rows],
        "obligations_total": sum(int(row.get("_obligations_total") or 0) for row in rows),
        "obligations_proved": sum(int(row.get("_obligations_proved") or 0) for row in rows),
    }
    return rows, summary


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
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_rows(args.source)
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
