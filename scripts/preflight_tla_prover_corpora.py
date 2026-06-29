#!/usr/bin/env python3
"""Preflight ChatTLA TLA prover corpora before spending GPU time."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.diagnose_sany_tlc_pass_corpus import diagnose_corpus

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = [
    REPO / "data" / "processed" / "tla_prover" / "chattla_tla_prover_sft_v1.jsonl",
    REPO / "data" / "processed" / "tla_prover" / "chattla_tla_prover_sft_public_expanded_v1.jsonl",
    REPO / "data" / "processed" / "tla_prover" / "chattla_tla_prover_sft_public_all_v1.jsonl",
    REPO / "data" / "processed" / "prover_eval.jsonl",
    REPO / "data" / "processed" / "formalllm_eval_v1.jsonl",
    REPO / "data" / "processed" / "ai4fm_public_tlaprove_import_v1.jsonl",
    REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.jsonl",
    REPO / "data" / "processed" / "ai4fm_public_seed_prover_candidates_v1.jsonl",
    REPO / "data" / "processed" / "sany_tlc_pass_sft_v1.jsonl",
    REPO / "data" / "processed" / "sany_tlc_pass_eval_v1.jsonl",
]
ALLOWED_ROLES = {"developer", "user", "assistant"}
ALLOWED_ASSISTANT_CHANNELS = {"analysis", "commentary", "final"}
MODULE_HEADER_RE = __import__("re").compile(r"(?m)^\s*-+\s*MODULE\s+([A-Za-z_]\w*)")
FORMALLLM_CORPUS = REPO / "data" / "processed" / "formalllm_eval_v1.jsonl"
PROVER_TRAIN_CORPUS_NAMES = {
    "chattla_tla_prover_sft_v1.jsonl",
    "chattla_tla_prover_sft_public_expanded_v1.jsonl",
    "chattla_tla_prover_sft_public_all_v1.jsonl",
}


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


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


def _check_direct_content_row(row: dict[str, Any], row_num: int, errors: list[str]) -> None:
    content = row.get("content")
    module = row.get("module")
    if not isinstance(content, str):
        _err(errors, row_num, "missing direct module content")
        return
    match = MODULE_HEADER_RE.search(content)
    if not match:
        _err(errors, row_num, "content missing module header")
        return
    header = match.group(1)
    if not isinstance(module, str) or not module.strip():
        _err(errors, row_num, "missing module field")
    elif module != header:
        _err(errors, row_num, f"module/header mismatch {module} != {header}")


def check_jsonl(path: Path, *, max_errors: int = 25) -> dict[str, Any]:
    errors: list[str] = []
    rows = 0
    if not path.exists():
        return {"path": _display_path(path), "ok": False, "rows": 0, "errors": [f"missing file: {_display_path(path)}"]}

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
                if isinstance(row.get("messages"), list):
                    _check_messages(row, row_num, errors)
                elif "content" in row or "module" in row:
                    _check_direct_content_row(row, row_num, errors)
                else:
                    _err(errors, row_num, "row matches neither messages corpus nor direct-content corpus schema")
            if len(errors) >= max_errors:
                errors.append("error limit reached")
                break
    return {"path": _display_path(path), "ok": not errors and rows > 0, "rows": rows, "errors": errors}


def _iter_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _fingerprint(row: dict[str, Any]) -> str:
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def inspect_formalllm_coverage(
    *,
    formalllm_path: Path,
    train_paths: list[Path],
) -> dict[str, Any]:
    formalllm_rows = _iter_rows(formalllm_path)
    expected = Counter(_fingerprint(row) for row in formalllm_rows)
    prompt_ids = {
        _fingerprint(row): str(row.get("_prompt_id", f"row-{idx+1}"))
        for idx, row in enumerate(formalllm_rows)
    }
    coverage: dict[str, Any] = {
        "formalllm_path": _display_path(formalllm_path),
        "formalllm_rows": len(formalllm_rows),
        "corpora": [],
    }
    overall_ok = True
    for path in train_paths:
        train_rows = _iter_rows(path)
        observed = Counter(_fingerprint(row) for row in train_rows)
        missing = [fingerprint for fingerprint, count in expected.items() if observed[fingerprint] < count]
        matched_distinct = sum(1 for fingerprint in expected if observed[fingerprint] >= expected[fingerprint])
        matched_total = sum(min(observed[fingerprint], count) for fingerprint, count in expected.items())
        extra_occurrences = sum(max(observed[fingerprint] - count, 0) for fingerprint, count in expected.items())
        item = {
            "path": _display_path(path),
            "rows": len(train_rows),
            "matched_distinct_rows": matched_distinct,
            "matched_total_occurrences": matched_total,
            "missing_rows": len(missing),
            "missing_prompt_ids_sample": [prompt_ids[fingerprint] for fingerprint in missing[:10]],
            "extra_occurrences_over_formalllm_rows": extra_occurrences,
            "ok": not missing,
        }
        overall_ok = overall_ok and item["ok"]
        coverage["corpora"].append(item)
    coverage["ok"] = overall_ok
    return coverage


def build_report(
    paths: list[Path],
    *,
    formalllm_path: Path = FORMALLLM_CORPUS,
    holdout: Path = REPO / "data" / "processed" / "diamond_eval_holdout.jsonl",
    sany_summary: Path | None = REPO / "data" / "processed" / "sany_tlc_pass_sft_v1.summary.json",
) -> dict[str, Any]:
    results = [check_jsonl(path) for path in paths]
    report: dict[str, Any] = {"ok": all(item["ok"] for item in results), "results": results}
    train_paths = [path for path in paths if path.name in PROVER_TRAIN_CORPUS_NAMES and path.exists()]
    selected_formalllm_path = next(
        (path for path in paths if path.name == formalllm_path.name and path.exists()),
        formalllm_path if formalllm_path.exists() else None,
    )
    if selected_formalllm_path is not None and train_paths:
        coverage = inspect_formalllm_coverage(
            formalllm_path=selected_formalllm_path,
            train_paths=train_paths,
        )
        report["formalllm_coverage"] = coverage
        report["ok"] = report["ok"] and coverage["ok"]
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
