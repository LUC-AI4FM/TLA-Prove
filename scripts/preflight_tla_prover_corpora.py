#!/usr/bin/env python3
"""Preflight ChatTLA TLA prover corpora before spending GPU time."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.diagnose_sany_tlc_pass_corpus import diagnose_corpus

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = [
    REPO / "data" / "processed" / "tla_prover" / "chattla_tla_prover_sft_v1.jsonl",
    REPO / "data" / "processed" / "prover_eval.jsonl",
    REPO / "data" / "processed" / "formalllm_eval_v1.jsonl",
    REPO / "data" / "processed" / "ai4fm_public_tlaprove_import_v1.jsonl",
    REPO / "data" / "processed" / "sany_tlc_pass_sft_v1.jsonl",
    REPO / "data" / "processed" / "sany_tlc_pass_eval_v1.jsonl",
]
ALLOWED_ROLES = {"developer", "user", "assistant"}
ALLOWED_ASSISTANT_CHANNELS = {"analysis", "commentary", "final"}


def _err(errors: list[str], row: int, message: str) -> None:
    errors.append(f"row {row}: {message}")


def _check_messages(row: dict[str, Any], row_num: int, errors: list[str]) -> None:
    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        _err(errors, row_num, "missing non-empty messages list")
        return

    has_user = False
    has_final = False
    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            _err(errors, row_num, f"message {idx} is not an object")
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role not in ALLOWED_ROLES:
            _err(errors, row_num, f"message {idx} has disallowed role {role}")
        if not isinstance(content, str) or not content.strip():
            _err(errors, row_num, f"message {idx} has empty content")
        if role == "user":
            has_user = True
        if role == "assistant":
            channel = msg.get("channel")
            if channel not in ALLOWED_ASSISTANT_CHANNELS:
                _err(errors, row_num, f"assistant message {idx} missing/invalid channel {channel}")
            if channel == "final":
                has_final = True
    if not has_user:
        _err(errors, row_num, "missing user message")
    if not has_final:
        _err(errors, row_num, "missing assistant final message")


def check_jsonl(path: Path, *, max_errors: int = 25) -> dict[str, Any]:
    errors: list[str] = []
    rows = 0
    if not path.exists():
        return {"path": str(path), "ok": False, "rows": 0, "errors": [f"missing file: {path}"]}

    with path.open(encoding="utf-8") as handle:
        for row_num, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                _err(errors, row_num, f"invalid json: {exc}")
                continue
            if not isinstance(row, dict):
                _err(errors, row_num, "row is not an object")
            else:
                _check_messages(row, row_num, errors)
            if len(errors) >= max_errors:
                errors.append("error limit reached")
                break
    return {"path": str(path), "ok": not errors and rows > 0, "rows": rows, "errors": errors}


def build_report(
    paths: list[Path],
    *,
    holdout: Path = REPO / "data" / "processed" / "diamond_eval_holdout.jsonl",
    sany_summary: Path | None = REPO / "data" / "processed" / "sany_tlc_pass_sft_v1.summary.json",
) -> dict[str, Any]:
    results = [check_jsonl(path) for path in paths]
    report: dict[str, Any] = {"ok": all(item["ok"] for item in results), "results": results}
    sany_paths = [path for path in paths if path.name == "sany_tlc_pass_sft_v1.jsonl"]
    if sany_paths:
        diagnostic = diagnose_corpus(corpus=sany_paths[0], holdout=holdout, summary=sany_summary)
        report["sany_tlc_diagnostic"] = diagnostic
        report["ok"] = report["ok"] and diagnostic["ok"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=DEFAULT_PATHS)
    parser.add_argument("--out", type=Path, default=REPO / "outputs" / "manifests" / "tla_prover_corpus_preflight.json")
    args = parser.parse_args()

    report = build_report(args.paths)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
