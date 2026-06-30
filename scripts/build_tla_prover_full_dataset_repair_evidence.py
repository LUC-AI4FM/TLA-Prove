#!/usr/bin/env python3
"""Link full-dataset repair rows to prompt/gold evidence already present in the repo."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REPAIR_QUEUE = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_repair_queue.jsonl"
DEFAULT_DIAMOND_HOLDOUT = REPO / "data" / "processed" / "diamond_eval_holdout.jsonl"
DEFAULT_FORMALLLM_EVAL = REPO / "data" / "processed" / "formalllm_eval_v1.jsonl"
DEFAULT_FORMALLLM_PUBLIC_MODULES = REPO / "data" / "processed" / "formalllm_public_tla_modules_v1.jsonl"
DEFAULT_PUBLIC_SEED_CANDIDATES = REPO / "data" / "processed" / "ai4fm_public_seed_prover_candidates_v1.jsonl"
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_full_dataset_repair_evidence.jsonl"


def _display_path(path: Path, repo: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text_if_exists(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _best_formalllm_public_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        module = str(row.get("module") or "").strip()
        content = str(row.get("content") or "").strip()
        if not module or not content:
            continue
        current = best.get(module)
        if current is None:
            best[module] = row
            continue
        current_path = str(current.get("source_path") or "")
        candidate_path = str(row.get("source_path") or "")
        current_key = (
            1 if current_path.endswith("_clean.tla") else 0,
            -len(str(current.get("content") or "")),
        )
        candidate_key = (
            1 if candidate_path.endswith("_clean.tla") else 0,
            -len(content),
        )
        if candidate_key > current_key:
            best[module] = row
    return best


def _best_public_seed_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        module = str(row.get("module") or "").strip()
        content = str(row.get("content") or "").strip()
        if not module or not content:
            continue
        current = best.get(module)
        if current is None:
            best[module] = row
            continue
        current_repo = str(current.get("repo") or "")
        candidate_repo = str(row.get("repo") or "")
        current_key = (
            1 if current_repo == "tlaplus/Examples" else 0,
            -len(str(current.get("content") or "")),
        )
        candidate_key = (
            1 if candidate_repo == "tlaplus/Examples" else 0,
            -len(content),
        )
        if candidate_key > current_key:
            best[module] = row
    return best


def _formalllm_prompt(messages: list[dict[str, Any]]) -> str | None:
    for message in messages:
        if str(message.get("role") or "") == "user":
            content = str(message.get("content") or "").strip()
            if content:
                return content
    return None


def _format_errors(row: dict[str, Any]) -> str:
    status = str(row.get("status") or "")
    if status == "tlaps_partial":
        tlapm = row.get("tlapm") or {}
        failed = int(tlapm.get("obligations_failed") or 0)
        total = int(tlapm.get("obligations_total") or 0)
        excerpt = str(row.get("failure_excerpt") or "").strip()
        detail = f"TLAPS partial proof: {failed}/{total} obligations failed."
        return "\n".join(part for part in [detail, excerpt] if part)
    if status == "tlc_error":
        family = str(row.get("tlc_error_family") or "").strip()
        excerpt = str(row.get("failure_excerpt") or "").strip()
        return "\n".join(part for part in [family, excerpt] if part)
    family = str(row.get("skip_reason_family") or "").strip()
    excerpt = str(row.get("failure_excerpt") or "").strip()
    return "\n".join(part for part in [family, excerpt] if part)


def _verify_summary(row: dict[str, Any]) -> str:
    status = str(row.get("status") or "")
    parts = [
        f"status={status}",
        f"bucket={row.get('repair_bucket', '')}",
        f"priority={row.get('repair_priority', '')}",
    ]
    tlapm = row.get("tlapm") or {}
    if tlapm:
        parts.append(f"obligations_failed={int(tlapm.get('obligations_failed') or 0)}")
        parts.append(f"obligations_total={int(tlapm.get('obligations_total') or 0)}")
    if row.get("tlc_error_family"):
        parts.append(f"tlc_error_family={row['tlc_error_family']}")
    if row.get("skip_reason_family"):
        parts.append(f"skip_reason_family={row['skip_reason_family']}")
    return " ".join(parts)


def _before_score(row: dict[str, Any]) -> float:
    status = str(row.get("status") or "")
    if status == "tlaps_partial":
        tlapm = row.get("tlapm") or {}
        total = float(tlapm.get("obligations_total") or 0)
        proved = float(tlapm.get("obligations_proved") or 0)
        return (proved / total) if total else 0.0
    if status == "not_inductive":
        return 0.35
    if status == "tlc_error":
        return 0.15
    return 0.05


def build_evidence(
    *,
    repair_queue: Path = DEFAULT_REPAIR_QUEUE,
    diamond_holdout: Path = DEFAULT_DIAMOND_HOLDOUT,
    formalllm_eval: Path = DEFAULT_FORMALLLM_EVAL,
    formalllm_public_modules: Path = DEFAULT_FORMALLLM_PUBLIC_MODULES,
    public_seed_candidates: Path = DEFAULT_PUBLIC_SEED_CANDIDATES,
    repo: Path = REPO,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    queue_rows = _load_jsonl(repair_queue)
    diamond_by_module = {str(row.get("module") or "").strip(): row for row in _load_jsonl(diamond_holdout)}
    formalllm_eval_by_module = {
        str(row.get("_module") or "").strip(): row
        for row in _load_jsonl(formalllm_eval)
        if str(row.get("_module") or "").strip()
    }
    formalllm_public_by_module = _best_formalllm_public_rows(_load_jsonl(formalllm_public_modules))
    public_seed_by_module = _best_public_seed_rows(_load_jsonl(public_seed_candidates))

    evidence_rows: list[dict[str, Any]] = []
    evidence_status_counts: Counter[str] = Counter()
    bucket_pair_ready_counts: Counter[str] = Counter()
    prompt_source_counts: Counter[str] = Counter()
    gold_source_counts: Counter[str] = Counter()
    status_by_bucket: dict[str, Counter[str]] = defaultdict(Counter)

    for row in queue_rows:
        module = str(row.get("module") or "").strip()
        module_path = Path(str(row.get("module_path") or ""))
        broken_spec = _read_text_if_exists(module_path) or ""

        nl: str | None = None
        prompt_source_kind: str | None = None
        prompt_source_path: str | None = None
        prompt_source_prompt_id: str | None = None

        gold_spec: str | None = None
        gold_source_kind: str | None = None
        gold_source_path: str | None = None
        gold_source_repo: str | None = None

        diamond_row = diamond_by_module.get(module)
        if diamond_row is not None:
            nl = str(diamond_row.get("topic_desc") or "").strip() or None
            prompt_source_kind = "diamond_eval_holdout"
            prompt_source_path = _display_path(diamond_holdout, repo)
            gold_spec = str(diamond_row.get("spec") or "").strip() or None
            gold_source_kind = "diamond_eval_holdout"
            gold_source_path = _display_path(diamond_holdout, repo)

        if (not nl or not gold_spec) and module in formalllm_eval_by_module:
            eval_row = formalllm_eval_by_module[module]
            candidate_prompt = _formalllm_prompt(list(eval_row.get("messages") or []))
            if candidate_prompt and not nl:
                nl = candidate_prompt
                prompt_source_kind = "formalllm_eval"
                prompt_source_path = _display_path(formalllm_eval, repo)
                prompt_source_prompt_id = str(eval_row.get("_prompt_id") or "").strip() or None

        if not gold_spec and module in formalllm_public_by_module:
            public_row = formalllm_public_by_module[module]
            gold_spec = str(public_row.get("content") or "").strip() or None
            gold_source_kind = "formalllm_public_module"
            gold_source_path = str(public_row.get("source_path") or "").strip() or None
            gold_source_repo = str(public_row.get("repo") or "").strip() or None

        if not gold_spec and module in public_seed_by_module:
            public_row = public_seed_by_module[module]
            gold_spec = str(public_row.get("content") or "").strip() or None
            gold_source_kind = "public_seed_candidate"
            gold_source_path = str(public_row.get("source_path") or "").strip() or None
            gold_source_repo = str(public_row.get("repo") or "").strip() or None

        if nl and gold_spec:
            evidence_status = "pair_ready"
        elif gold_spec:
            evidence_status = "reference_spec_only"
        elif nl:
            evidence_status = "prompt_only"
        else:
            evidence_status = "no_evidence"

        bucket = str(row.get("repair_bucket") or "")
        evidence_status_counts[evidence_status] += 1
        status_by_bucket[bucket][evidence_status] += 1
        if evidence_status == "pair_ready":
            bucket_pair_ready_counts[bucket] += 1
        if prompt_source_kind:
            prompt_source_counts[prompt_source_kind] += 1
        if gold_source_kind:
            gold_source_counts[gold_source_kind] += 1

        evidence_rows.append(
            {
                **row,
                "broken_spec_path": _display_path(module_path, repo),
                "broken_spec_chars": len(broken_spec),
                "broken_spec_sha256": _sha256_text(broken_spec) if broken_spec else None,
                "nl": nl,
                "prompt_source_kind": prompt_source_kind,
                "prompt_source_path": prompt_source_path,
                "prompt_source_prompt_id": prompt_source_prompt_id,
                "gold_source_kind": gold_source_kind,
                "gold_source_path": gold_source_path,
                "gold_source_repo": gold_source_repo,
                "repaired_spec": gold_spec,
                "repaired_spec_chars": len(gold_spec or ""),
                "repaired_spec_sha256": _sha256_text(gold_spec) if gold_spec else None,
                "errors_rendered": _format_errors(row),
                "verify_summary": _verify_summary(row),
                "before_score": _before_score(row),
                "evidence_status": evidence_status,
                "pair_ready": evidence_status == "pair_ready",
            }
        )

    evidence_rows.sort(
        key=lambda item: (
            str(item.get("repair_priority") or ""),
            str(item.get("repair_bucket") or ""),
            str(item.get("module") or "").lower(),
            str(item.get("module_path") or "").lower(),
        )
    )

    summary = {
        "schema": "chattla_tla_prover_full_dataset_repair_evidence_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repair_queue_path": _display_path(repair_queue, repo),
        "rows": len(evidence_rows),
        "pair_ready_rows": evidence_status_counts.get("pair_ready", 0),
        "evidence_status_counts": dict(sorted(evidence_status_counts.items())),
        "bucket_pair_ready_counts": dict(sorted(bucket_pair_ready_counts.items())),
        "status_by_bucket": {bucket: dict(sorted(counter.items())) for bucket, counter in sorted(status_by_bucket.items())},
        "prompt_source_counts": dict(sorted(prompt_source_counts.items())),
        "gold_source_counts": dict(sorted(gold_source_counts.items())),
        "recommended_next_step": (
            "Build a repair-pair corpus from pair_ready rows first, then decide whether to backfill prompt-only/reference-only rows."
        ),
    }
    return evidence_rows, summary


def _write_outputs(*, rows: list[dict[str, Any]], summary: dict[str, Any], out: Path, repo: Path = REPO) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    summary_path = out.with_suffix(".summary.json")
    final_summary = dict(summary)
    final_summary["out"] = _display_path(out, repo)
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-queue", type=Path, default=DEFAULT_REPAIR_QUEUE)
    parser.add_argument("--diamond-holdout", type=Path, default=DEFAULT_DIAMOND_HOLDOUT)
    parser.add_argument("--formalllm-eval", type=Path, default=DEFAULT_FORMALLLM_EVAL)
    parser.add_argument("--formalllm-public-modules", type=Path, default=DEFAULT_FORMALLLM_PUBLIC_MODULES)
    parser.add_argument("--public-seed-candidates", type=Path, default=DEFAULT_PUBLIC_SEED_CANDIDATES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_evidence(
        repair_queue=args.repair_queue,
        diamond_holdout=args.diamond_holdout,
        formalllm_eval=args.formalllm_eval,
        formalllm_public_modules=args.formalllm_public_modules,
        public_seed_candidates=args.public_seed_candidates,
    )
    final_summary = _write_outputs(rows=rows, summary=summary, out=args.out, repo=REPO)
    print(json.dumps({"out": _display_path(args.out, REPO), "summary": final_summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
