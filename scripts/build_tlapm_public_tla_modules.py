#!/usr/bin/env python3
"""Build a usable public TLAPM library `.tla` module corpus from a local clone."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_TLAPM_ROOT = REPO / "data" / "external" / "tlapm"
DEFAULT_OUT = REPO / "data" / "processed" / "tlapm_public_tla_modules_v1.jsonl"
MODULE_RE = __import__("re").compile(r"(?m)^\s*-+\s*MODULE\s+([A-Za-z_]\w*)")
CURATED_EXAMPLE_HELPERS = (
    Path("examples/paxos/Consensus.tla"),
)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _module_name(text: str) -> str | None:
    match = MODULE_RE.search(text)
    return match.group(1) if match else None


def _git_head_sha(root: Path) -> str | None:
    git_dir = root / ".git"
    if not git_dir.exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def build_tlapm_tla_modules(
    *,
    tlapm_root: Path = DEFAULT_TLAPM_ROOT,
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    library_root = tlapm_root / "library"
    tla_paths = sorted(library_root.glob("*.tla"))
    curated_paths = [tlapm_root / rel for rel in CURATED_EXAMPLE_HELPERS if (tlapm_root / rel).exists()]
    tla_paths.extend(path for path in curated_paths if path not in tla_paths)
    rows: list[dict[str, Any]] = []
    duplicate_modules: Counter[str] = Counter()
    skipped_missing_module_header = 0
    repo_head_sha = _git_head_sha(tlapm_root)

    for path in tla_paths:
        content = path.read_text(encoding="utf-8", errors="replace")
        module = _module_name(content)
        if not module:
            skipped_missing_module_header += 1
            continue
        duplicate_modules[module] += 1
        rows.append(
            {
                "repo": "tlaplus/tlapm",
                "repo_head_sha": repo_head_sha,
                "module": module,
                "source_path": _display_path(path),
                "content": content,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )

    rows.sort(key=lambda row: (str(row.get("module", "")).lower(), str(row.get("source_path", "")).lower()))
    summary = {
        "schema": "chattla_tlapm_public_tla_modules_v1",
        "generated_at": generated_at,
        "tlapm_root": _display_path(tlapm_root),
        "library_root": _display_path(library_root),
        "repo_head_sha": repo_head_sha,
        "tla_candidates": len(tla_paths),
        "curated_example_candidates": len(curated_paths),
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
    parser.add_argument("--tlapm-root", type=Path, default=DEFAULT_TLAPM_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_tlapm_tla_modules(tlapm_root=args.tlapm_root)
    report = write_outputs(rows, summary, args.out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
