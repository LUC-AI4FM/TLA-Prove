#!/usr/bin/env python3
"""Import public AI4FM TLA-Prove corpora into a normalized ChatTLA JSONL artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.build_sany_tlc_pass_corpus import DEVELOPER_PROMPT, _with_tlc_config
from scripts.build_tla_prover_finetune_corpus import normalize_messages
from scripts.inspect_ai4fm_public_tlaprove_corpora import API_ROOT, RAW_ROOT
from src.postprocess.normalize import normalize_spec

DEFAULT_OUT = REPO / "data" / "processed" / "ai4fm_public_tlaprove_import_v1.jsonl"
MODULE_RE = re.compile(r"(?m)^\s*-+\s*MODULE\s+([A-Za-z0-9_]+)\s*-+")
URL_TIMEOUT = 60


BASE_SOURCE_SPECS: tuple[tuple[str, dict[str, str]], ...] = (
    (
        "processed_train",
        {
            "kind": "messages",
            "path": "data/processed/train.jsonl",
            "url": f"{RAW_ROOT}/data/processed/train.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_sft_v3",
        {
            "kind": "messages",
            "path": "data/processed/diamond_sft_v3.jsonl",
            "url": f"{RAW_ROOT}/data/processed/diamond_sft_v3.jsonl",
            "split": "train",
        },
    ),
    (
        "processed_eval",
        {
            "kind": "messages",
            "path": "data/processed/eval.jsonl",
            "url": f"{RAW_ROOT}/data/processed/eval.jsonl",
            "split": "eval",
        },
    ),
    (
        "diamond_eval_holdout",
        {
            "kind": "holdout",
            "path": "data/processed/diamond_eval_holdout.jsonl",
            "url": f"{RAW_ROOT}/data/processed/diamond_eval_holdout.jsonl",
            "split": "eval",
        },
    ),
    (
        "ralph_train",
        {
            "kind": "ralph",
            "path": "data/frs_tla_ralph_gen/train.jsonl",
            "url": f"{RAW_ROOT}/data/frs_tla_ralph_gen/train.jsonl",
            "split": "train",
        },
    ),
    (
        "ralph_dev",
        {
            "kind": "ralph",
            "path": "data/frs_tla_ralph_gen/dev.jsonl",
            "url": f"{RAW_ROOT}/data/frs_tla_ralph_gen/dev.jsonl",
            "split": "eval",
        },
    ),
)
ADDITIONAL_PUBLIC_SOURCE_SPECS: tuple[tuple[str, dict[str, str]], ...] = (
    (
        "toy_train",
        {
            "kind": "messages",
            "path": "data/toy/train.jsonl",
            "url": f"{RAW_ROOT}/data/toy/train.jsonl",
            "split": "train",
        },
    ),
    (
        "toy_eval",
        {
            "kind": "messages",
            "path": "data/toy/eval.jsonl",
            "url": f"{RAW_ROOT}/data/toy/eval.jsonl",
            "split": "eval",
        },
    ),
    (
        "diamond_gen_communication_protocols",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/communication_protocols.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/communication_protocols.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_concurrency_primitives",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/concurrency_primitives.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/concurrency_primitives.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_consensus_election",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/consensus_election.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/consensus_election.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_data_structures",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/data_structures.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/data_structures.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_diamond_generated",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/diamond_generated.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/diamond_generated.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_memory_caches",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/memory_caches.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/memory_caches.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_mutual_exclusion",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/mutual_exclusion.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/mutual_exclusion.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_puzzles_classical",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/puzzles_classical.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/puzzles_classical.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_scheduling_resources",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/scheduling_resources.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/scheduling_resources.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_transactions_databases",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/transactions_databases.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/transactions_databases.jsonl",
            "split": "train",
        },
    ),
    (
        "diamond_gen_workflows_state_machines",
        {
            "kind": "holdout",
            "path": "outputs/diamond_gen/workflows_state_machines.jsonl",
            "url": f"{RAW_ROOT}/outputs/diamond_gen/workflows_state_machines.jsonl",
            "split": "train",
        },
    ),
)


def source_specs(*, include_additional_public_jsonl: bool = False) -> OrderedDict[str, dict[str, str]]:
    specs = OrderedDict(BASE_SOURCE_SPECS)
    if include_additional_public_jsonl:
        specs.update(OrderedDict(ADDITIONAL_PUBLIC_SOURCE_SPECS))
    return specs


def _load_json_url(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=URL_TIMEOUT) as response:
        return json.load(response)


def _load_jsonl_url(url: str) -> list[dict[str, Any]]:
    rows = []
    with urllib.request.urlopen(url, timeout=URL_TIMEOUT) as response:
        for line in response.read().decode("utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _canonical_text(text: str) -> str:
    normalized, _ = normalize_spec(text.replace("\r\n", "\n"))
    return normalized.strip()


def _module_name(spec_text: str) -> str | None:
    match = MODULE_RE.search(spec_text)
    return match.group(1) if match else None


def _normalize_final_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    normalized = normalize_messages(messages)
    assistant_indexes = [i for i, msg in enumerate(normalized) if msg.get("role") == "assistant"]
    if not assistant_indexes:
        raise ValueError("missing assistant messages")
    final_idx = assistant_indexes[-1]
    normalized[final_idx]["content"] = _with_tlc_config(normalized[final_idx]["content"])
    return normalized, normalized[final_idx]["content"]


def _base_metadata(*, corpus_name: str, split: str, path: str, final_text: str) -> dict[str, Any]:
    return {
        "_module": _module_name(final_text),
        "_canonical_final_sha256": hashlib.sha256(_canonical_text(final_text).encode("utf-8")).hexdigest(),
        "_ai4fm_public_corpora": [corpus_name],
        "_ai4fm_public_paths": [path],
        "_ai4fm_public_splits": [split],
    }


def _normalize_messages_row(row: dict[str, Any], *, corpus_name: str, spec: dict[str, str]) -> dict[str, Any]:
    messages, final_text = _normalize_final_messages(row["messages"])
    out = dict(row)
    out["messages"] = messages
    out.update(_base_metadata(corpus_name=corpus_name, split=spec["split"], path=spec["path"], final_text=final_text))
    if not out.get("_source"):
        out["_source"] = f"ai4fm_public_tlaprove/{corpus_name}"
    return out


def _normalize_holdout_row(row: dict[str, Any], *, corpus_name: str, spec: dict[str, str]) -> dict[str, Any]:
    module = row.get("module") or "ImportedHoldout"
    messages = [
        {"role": "developer", "content": DEVELOPER_PROMPT},
        {
            "role": "user",
            "content": f"Write a TLA+ specification for the following:\n\n{row['topic_desc']}\n",
        },
        {
            "role": "assistant",
            "channel": "analysis",
            "content": (
                f"I'll write module {module} with finite state domains, Init, Next, Spec, "
                "and TypeOK so it parses with SANY and passes TLC."
            ),
        },
        {"role": "assistant", "channel": "final", "content": _with_tlc_config(row["spec"])},
    ]
    final_text = messages[-1]["content"]
    return {
        "_source": f"ai4fm_public_tlaprove/{corpus_name}",
        "_tier": row.get("tier"),
        "_module": row.get("module") or _module_name(final_text),
        "_semantic": row.get("batch"),
        "_evidence": {
            "sany_pass": row.get("sany_pass"),
            "is_diamond": row.get("is_diamond"),
            "mutation_caught": row.get("mutation_caught"),
            "trivial_invariant": row.get("trivial_invariant"),
            "distinct_states": row.get("distinct_states"),
            "invariants_checked": row.get("invariants_checked"),
        },
        "messages": messages,
        **_base_metadata(corpus_name=corpus_name, split=spec["split"], path=spec["path"], final_text=final_text),
    }


def _normalize_ralph_row(row: dict[str, Any], *, corpus_name: str, spec: dict[str, str]) -> dict[str, Any]:
    final_text = _with_tlc_config(row["reference"])
    module = _module_name(final_text)
    return {
        "_source": row.get("source") or f"ai4fm_public_tlaprove/{corpus_name}",
        "_tier": "public_ralph",
        "_module": module,
        "_difficulty": row.get("difficulty"),
        "_topic": row.get("topic"),
        "_spec_id": row.get("spec_id"),
        "_normalized_sha1": row.get("normalized_sha1"),
        "_coverage": row.get("coverage"),
        "_kill_rate": row.get("kill_rate"),
        "_aux_modules": row.get("aux_modules"),
        "messages": [
            {"role": "developer", "content": DEVELOPER_PROMPT},
            {"role": "user", "content": row["prompt"]},
            {
                "role": "assistant",
                "channel": "analysis",
                "content": (
                    f"I'll write module {module or 'ImportedRalphModule'} with Init, Next, Spec, "
                    "and TypeOK so it is valid TLA+ and ready for TLC."
                ),
            },
            {"role": "assistant", "channel": "final", "content": final_text},
        ],
        **_base_metadata(corpus_name=corpus_name, split=spec["split"], path=spec["path"], final_text=final_text),
    }


def _normalize_row(row: dict[str, Any], *, corpus_name: str, spec: dict[str, str]) -> dict[str, Any]:
    if spec["kind"] == "messages":
        return _normalize_messages_row(row, corpus_name=corpus_name, spec=spec)
    if spec["kind"] == "holdout":
        return _normalize_holdout_row(row, corpus_name=corpus_name, spec=spec)
    if spec["kind"] == "ralph":
        return _normalize_ralph_row(row, corpus_name=corpus_name, spec=spec)
    raise ValueError(f"unsupported corpus kind {spec['kind']}")


def _merge_provenance(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    for field in ("_ai4fm_public_corpora", "_ai4fm_public_paths", "_ai4fm_public_splits"):
        existing[field] = sorted({*existing.get(field, []), *incoming.get(field, [])})
    if not existing.get("_module") and incoming.get("_module"):
        existing["_module"] = incoming["_module"]


def build_import(
    source_rows: dict[str, list[dict[str, Any]]],
    *,
    repo: dict[str, Any] | None = None,
    generated_at: str | None = None,
    dedupe: bool = True,
    include_additional_public_jsonl: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    kept: list[dict[str, Any]] = []
    by_hash: dict[str, dict[str, Any]] = {}
    per_corpus: dict[str, dict[str, Any]] = {}
    raw_rows = 0

    for corpus_name, spec in source_specs(include_additional_public_jsonl=include_additional_public_jsonl).items():
        rows = source_rows.get(corpus_name, [])
        seen_in_corpus: set[str] = set()
        stats = {
            "path": spec["path"],
            "kind": spec["kind"],
            "split": spec["split"],
            "raw_rows": len(rows),
            "kept_rows": 0,
            "duplicate_rows_collapsed": 0,
            "unique_canonical_finals": 0,
        }
        for row in rows:
            raw_rows += 1
            normalized = _normalize_row(row, corpus_name=corpus_name, spec=spec)
            dedupe_key = normalized["_canonical_final_sha256"]
            seen_in_corpus.add(dedupe_key)
            if dedupe and dedupe_key in by_hash:
                stats["duplicate_rows_collapsed"] += 1
                _merge_provenance(by_hash[dedupe_key], normalized)
                continue
            if dedupe:
                by_hash[dedupe_key] = normalized
            kept.append(normalized)
            stats["kept_rows"] += 1
        stats["unique_canonical_finals"] = len(seen_in_corpus)
        per_corpus[corpus_name] = stats

    summary = {
        "schema": "chattla_ai4fm_public_tlaprove_import_v1",
        "generated_at": generated_at,
        "repo": repo,
        "raw_rows": raw_rows,
        "kept_rows": len(kept),
        "duplicate_rows_collapsed": (raw_rows - len(kept)) if dedupe else 0,
        "dedupe_exact_final_spec": dedupe,
        "include_additional_public_jsonl": include_additional_public_jsonl,
        "per_corpus": per_corpus,
    }
    return kept, summary


def load_public_rows(*, include_additional_public_jsonl: bool = False) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    repo_meta = _load_json_url(API_ROOT)
    branch = repo_meta["default_branch"]
    branch_meta = _load_json_url(f"{API_ROOT}/branches/{branch}")
    repo = {
        "nameWithOwner": repo_meta["full_name"],
        "html_url": repo_meta["html_url"],
        "default_branch": branch,
        "head_sha": branch_meta["commit"]["sha"],
    }
    rows = {
        name: _load_jsonl_url(spec["url"])
        for name, spec in source_specs(include_additional_public_jsonl=include_additional_public_jsonl).items()
    }
    return rows, repo


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    final_summary = dict(summary)
    final_summary["out"] = str(out.relative_to(REPO)) if out.is_relative_to(REPO) else str(out)
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_summary["summary"] = (
        str(summary_path.relative_to(REPO)) if summary_path.is_relative_to(REPO) else str(summary_path)
    )
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="Preserve raw public rows instead of collapsing exact final-spec duplicates.",
    )
    parser.add_argument(
        "--include-additional-public-jsonl",
        action="store_true",
        help="Also ingest the currently excluded public data/toy and outputs/diamond_gen JSONL files.",
    )
    args = parser.parse_args()

    rows_by_corpus, repo = load_public_rows(
        include_additional_public_jsonl=args.include_additional_public_jsonl
    )
    rows, summary = build_import(
        rows_by_corpus,
        repo=repo,
        dedupe=not args.keep_duplicates,
        include_additional_public_jsonl=args.include_additional_public_jsonl,
    )
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
