#!/usr/bin/env python3
"""Build a usable public FormaLLM `.tla` module corpus from the checked-in repo."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_FORMALLLM_ROOT = REPO / "data" / "FormaLLM" / "data"
DEFAULT_OUT = REPO / "data" / "processed" / "formalllm_public_tla_modules_v1.jsonl"
MODULE_RE = __import__("re").compile(r"(?m)^\s*-+\s*MODULE\s+([A-Za-z_]\w*)")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _module_name(text: str) -> str | None:
    match = MODULE_RE.search(text)
    return match.group(1) if match else None


def _family(path: Path, *, formalllm_root: Path) -> str | None:
    rel = path.relative_to(formalllm_root)
    return rel.parts[0] if rel.parts else None


def build_formalllm_tla_modules(
    *,
    formalllm_root: Path = DEFAULT_FORMALLLM_ROOT,
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    tla_paths = sorted(formalllm_root.rglob("*.tla"))
    rows: list[dict[str, Any]] = []
    duplicate_modules: Counter[str] = Counter()
    skipped_missing_module_header = 0

    for path in tla_paths:
        content = path.read_text(encoding="utf-8", errors="replace")
        module = _module_name(content)
        if not module:
            skipped_missing_module_header += 1
            continue
        duplicate_modules[module] += 1
        rows.append(
            {
                "repo": "formalllm/public",
                "module": module,
                "family": _family(path, formalllm_root=formalllm_root),
                "source_path": _display_path(path),
                "content": content,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )

    rows.sort(key=lambda row: (str(row.get("module", "")).lower(), str(row.get("source_path", "")).lower()))
    summary = {
        "schema": "chattla_formalllm_public_tla_modules_v1",
        "generated_at": generated_at,
        "formalllm_root": _display_path(formalllm_root),
        "tla_candidates": len(tla_paths),
        "kept_rows": len(rows),
        "skipped_missing_module_header": skipped_missing_module_header,
        "duplicate_modules": {name: count for name, count in sorted(duplicate_modules.items()) if count > 1},
    }
    return rows, summary


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    final_summary = dict(summary)
    final_summary["out"] = _display_path(out)
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_summary["summary"] = _display_path(summary_path)
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formalllm-root", type=Path, default=DEFAULT_FORMALLLM_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_formalllm_tla_modules(formalllm_root=args.formalllm_root)
    report = write_outputs(rows, summary, args.out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
