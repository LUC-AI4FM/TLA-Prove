#!/usr/bin/env python3
"""Build a usable public AI4FM `.tla` module corpus from the seed-file manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO / "data" / "processed" / "ai4fm_public_seed_file_manifest_v1.jsonl"
DEFAULT_OUT = REPO / "data" / "processed" / "ai4fm_public_seed_tla_modules_v1.jsonl"
MODULE_RE = __import__("re").compile(r"(?m)^\s*-+\s*MODULE\s+([A-Za-z_]\w*)")
URL_TIMEOUT = 60


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=URL_TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def _module_name(text: str) -> str | None:
    match = MODULE_RE.search(text)
    return match.group(1) if match else None


def build_seed_tla_modules(
    manifest_path: Path,
    *,
    fetch_text: Callable[[str], str] = _fetch_text,
    generated_at: str | None = None,
    limit: int = 0,
    workers: int = 8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_rows = _load_jsonl(manifest_path)
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    skipped_non_tla = 0
    skipped_missing_module_header = 0
    fetch_failures = 0
    module_names: Counter[str] = Counter()
    tla_candidates: list[dict[str, Any]] = []

    for item in manifest_rows:
        if str(item.get("ext", "")).lower() != ".tla":
            skipped_non_tla += 1
            continue
        tla_candidates.append(item)
        if limit and len(tla_candidates) >= limit:
            break

    def process_item(item: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        url = str(item["download_url"])
        try:
            content = fetch_text(url)
        except Exception:
            return "fetch_failed", None
        module = _module_name(content)
        if not module:
            return "missing_module_header", None
        return (
            "ok",
            {
                "repo": item.get("repo"),
                "repo_head_sha": item.get("repo_head_sha"),
                "default_branch": item.get("default_branch"),
                "source_path": item.get("path"),
                "module": module,
                "download_url": url,
                "html_url": item.get("html_url"),
                "content": content,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            },
        )

    max_workers = max(1, workers)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for status, payload in executor.map(process_item, tla_candidates):
            if status == "fetch_failed":
                fetch_failures += 1
                continue
            if status == "missing_module_header":
                skipped_missing_module_header += 1
                continue
            assert payload is not None
            module_names[str(payload["module"])] += 1
            rows.append(payload)

    rows.sort(key=lambda row: (str(row.get("module", "")).lower(), str(row.get("repo", "")).lower(), str(row.get("source_path", "")).lower()))
    summary = {
        "schema": "chattla_ai4fm_public_seed_tla_modules_v1",
        "generated_at": generated_at,
        "manifest_path": str(manifest_path.relative_to(REPO)) if manifest_path.is_relative_to(REPO) else str(manifest_path),
        "manifest_rows": len(manifest_rows),
        "tla_candidates": len(tla_candidates),
        "kept_rows": len(rows),
        "skipped_non_tla": skipped_non_tla,
        "skipped_missing_module_header": skipped_missing_module_header,
        "fetch_failures": fetch_failures,
        "duplicate_modules": {name: count for name, count in sorted(module_names.items()) if count > 1},
        "workers": max_workers,
    }
    return rows, summary


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
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    rows, summary = build_seed_tla_modules(args.manifest, limit=args.limit, workers=args.workers)
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
