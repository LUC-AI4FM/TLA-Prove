#!/usr/bin/env python3
"""Build deterministic synthetic repair pairs from checked-in prover gold corpora."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.postprocess import normalize_spec

DEFAULT_GOLD = REPO / "data" / "processed" / "tla_prover" / "chattla_tla_prover_sft_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "tla_prover_synthetic_repair_pairs_v1.jsonl"


def _extract_final_spec(record: dict[str, Any]) -> str | None:
    for message in record.get("messages", []):
        if message.get("role") == "assistant" and message.get("channel") == "final":
            return str(message.get("content", "")).strip()
    return None


def _extract_user_text(record: dict[str, Any]) -> str | None:
    for message in record.get("messages", []):
        if message.get("role") == "user":
            return str(message.get("content", "")).strip()
    return None


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _hash_index(key: str, size: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % size


def _replace_definition(spec: str, name: str, new_body: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf"(?ms)^({re.escape(name)}\s*==\s*)(.*?)(?=^\w[\w\s]*==|\Z|^====\s*$)"
    )
    match = pattern.search(spec)
    if not match:
        return spec, False
    replaced = spec[:match.start()] + f"{name} == {new_body}\n" + spec[match.end():]
    return replaced, True


def _mutate_think(spec: str) -> str:
    return "<think>Repairing the module.</think>\n" + spec


def _mutate_fence(spec: str) -> str:
    return f"```tla\n{spec}\n```"


def _mutate_duplicate_module_header(spec: str) -> str | None:
    match = re.search(r"^(-{2,}\s*MODULE\s+\w+\s*-{2,})", spec, re.MULTILINE)
    if not match:
        return None
    return spec.replace(match.group(1), match.group(1) + "\n" + match.group(1), 1)


def _mutate_semicolons(spec: str) -> str | None:
    lines = spec.splitlines()
    candidates = [i for i, line in enumerate(lines) if re.search(r"==|/\\|UNCHANGED", line)]
    if not candidates:
        return None
    for index in candidates[: min(3, len(candidates))]:
        lines[index] = lines[index].rstrip() + ";"
    return "\n".join(lines)


def _mutate_drop_terminator(spec: str) -> str | None:
    new = re.sub(r"\n?====\s*$", "", spec.rstrip(), count=1)
    if new == spec.rstrip():
        return None
    return new


def _mutate_remove_extends(spec: str) -> str | None:
    new, count = re.subn(r"^EXTENDS\s+.*\n", "", spec, count=1, flags=re.MULTILINE)
    if count == 0:
        return None
    return new


def _mutate_drop_unchanged(spec: str) -> str | None:
    new, count = re.subn(r"/\\\s*UNCHANGED\s*<<[^>]+>>", "", spec, count=1)
    if count == 0:
        return None
    return new


def _mutate_typeok_true(spec: str) -> str | None:
    new, changed = _replace_definition(spec, "TypeOK", "TRUE")
    return new if changed else None


def _mutate_init_false(spec: str) -> str | None:
    new, changed = _replace_definition(spec, "Init", "FALSE")
    return new if changed else None


def _mutate_next_false(spec: str) -> str | None:
    new, changed = _replace_definition(spec, "Next", "FALSE")
    return new if changed else None


def _mutate_spec_empty_frame(spec: str) -> str | None:
    new, changed = _replace_definition(spec, "Spec", r"Init /\ [][Next]_<<>>")
    return new if changed else None


MutationFn = Callable[[str], str | None]

MUTATIONS: list[dict[str, Any]] = [
    {
        "name": "think_block",
        "difficulty": "easy",
        "before_score": 0.05,
        "diagnostic": "SANY parse error: unexpected <think> block before the module header.",
        "fn": lambda spec: _mutate_think(spec),
    },
    {
        "name": "markdown_fence",
        "difficulty": "easy",
        "before_score": 0.05,
        "diagnostic": "SANY parse error: markdown fences are not valid TLA+ syntax.",
        "fn": lambda spec: _mutate_fence(spec),
    },
    {
        "name": "duplicate_module_header",
        "difficulty": "easy",
        "before_score": 0.05,
        "diagnostic": "SANY parse error: duplicate MODULE header found in the same file.",
        "fn": _mutate_duplicate_module_header,
    },
    {
        "name": "semicolons",
        "difficulty": "easy",
        "before_score": 0.07,
        "diagnostic": "SANY parse error: semicolon-terminated TLA+ definitions are invalid.",
        "fn": _mutate_semicolons,
    },
    {
        "name": "drop_terminator",
        "difficulty": "easy",
        "before_score": 0.07,
        "diagnostic": "SANY parse error: module terminator `====` is missing.",
        "fn": _mutate_drop_terminator,
    },
    {
        "name": "remove_extends",
        "difficulty": "medium",
        "before_score": 0.18,
        "diagnostic": "Verifier summary: imported operators are now undefined because the EXTENDS line is missing.",
        "fn": _mutate_remove_extends,
    },
    {
        "name": "drop_unchanged",
        "difficulty": "medium",
        "before_score": 0.24,
        "diagnostic": "Verifier summary: one Next branch no longer frames untouched variables with UNCHANGED.",
        "fn": _mutate_drop_unchanged,
    },
    {
        "name": "typeok_true",
        "difficulty": "hard",
        "before_score": 0.48,
        "diagnostic": "Verifier summary: TypeOK was weakened to TRUE and no longer constrains the state space.",
        "fn": _mutate_typeok_true,
    },
    {
        "name": "init_false",
        "difficulty": "hard",
        "before_score": 0.52,
        "diagnostic": "Verifier summary: Init was replaced with FALSE, so the spec has no reachable initial states.",
        "fn": _mutate_init_false,
    },
    {
        "name": "next_false",
        "difficulty": "hard",
        "before_score": 0.44,
        "diagnostic": "Verifier summary: Next was replaced with FALSE, so the system cannot take any steps.",
        "fn": _mutate_next_false,
    },
    {
        "name": "spec_empty_frame",
        "difficulty": "hard",
        "before_score": 0.46,
        "diagnostic": "Verifier summary: Spec now uses an empty frame, so it no longer tracks the module variables correctly.",
        "fn": _mutate_spec_empty_frame,
    },
]


def _apply_mutation(spec: str, key: str) -> tuple[dict[str, Any], str]:
    start = _hash_index(key, len(MUTATIONS))
    for offset in range(len(MUTATIONS)):
        mutation = MUTATIONS[(start + offset) % len(MUTATIONS)]
        broken = mutation["fn"](spec)
        if broken and broken.strip() != spec.strip():
            return mutation, broken.strip()
    fallback = MUTATIONS[0]
    return fallback, fallback["fn"](spec).strip()


def build_rows(gold_path: Path = DEFAULT_GOLD, *, limit: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mutation_counts = {item["name"]: 0 for item in MUTATIONS}
    difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
    source_rows = 0
    skipped_rows = 0

    with gold_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            source_rows += 1
            record = json.loads(raw_line)
            final_spec = _extract_final_spec(record)
            user_text = _extract_user_text(record)
            if not final_spec or not user_text:
                skipped_rows += 1
                continue
            cleaned_spec, _ = normalize_spec(final_spec)
            if not re.search(r"^----\s*MODULE\s+\w+", cleaned_spec, re.MULTILINE):
                skipped_rows += 1
                continue

            prompt_id = str(record.get("_prompt_id") or f"row_{source_rows}")
            spec_hash = hashlib.sha256(cleaned_spec.encode("utf-8")).hexdigest()[:12]
            mutation, broken = _apply_mutation(cleaned_spec, prompt_id)
            mutation_counts[mutation["name"]] += 1
            difficulty_counts[mutation["difficulty"]] += 1
            rows.append(
                {
                    "repair_id": f"{prompt_id}::{spec_hash}::synthetic::{mutation['name']}",
                    "nl": user_text,
                    "broken_spec": broken,
                    "errors_rendered": mutation["diagnostic"],
                    "verify_summary": (
                        f"synthetic mutation={mutation['name']} "
                        f"difficulty={mutation['difficulty']} "
                        f"partial={float(mutation['before_score']):.3f}"
                    ),
                    "before_score": float(mutation["before_score"]),
                    "repaired_spec": cleaned_spec.strip(),
                    "after_score": 1.0,
                    "before_diamond": False,
                    "after_diamond": True,
                    "before_phase": "synthetic_mutation",
                    "after_phase": "gold_reference",
                    "before_failure_family": f"synthetic_{mutation['difficulty']}",
                    "after_failure_family": "gold",
                    "source_file": _display_path(gold_path),
                    "source_prompt_id": prompt_id,
                    "source_spec_sha256": spec_hash,
                    "mutation": mutation["name"],
                    "difficulty": mutation["difficulty"],
                }
            )
            if limit is not None and len(rows) >= limit:
                break

    rows.sort(key=lambda item: (float(item["before_score"]), str(item["repair_id"])))
    summary = {
        "schema": "chattla_tla_prover_synthetic_repair_pairs_summary_v1",
        "source": _display_path(gold_path),
        "source_rows": source_rows,
        "rows": len(rows),
        "skipped_rows": skipped_rows,
        "mutation_counts": {name: count for name, count in mutation_counts.items() if count},
        "difficulty_counts": difficulty_counts,
    }
    return rows, summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    rows, summary = build_rows(args.gold, limit=args.limit)
    _write_jsonl(args.out, rows)
    final_summary = dict(summary)
    final_summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    final_summary["out"] = _display_path(args.out)
    summary_path = args.out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "summary": final_summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
