#!/usr/bin/env python3
"""Materialize the public FormaLLM file/module surface as a JSONL manifest."""
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
DEFAULT_FORMALLLM_ROOT = REPO / "data" / "FormaLLM" / "data"
DEFAULT_OUT = REPO / "data" / "processed" / "formalllm_public_module_manifest_v1.jsonl"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _git_head(repo: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.SubprocessError:
        return None
    return completed.stdout.strip() or None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _classify(path: Path, *, formalllm_root: Path) -> str:
    rel = path.relative_to(formalllm_root.parent)
    parts = rel.parts
    if path.suffix == ".tla":
        if len(parts) >= 4 and parts[0] == "data" and parts[2] == "tla":
            return "canonical_clean_tla" if path.stem.endswith("_clean") else "canonical_variant_tla"
        return "auxiliary_tla"
    if path.suffix == ".cfg":
        if len(parts) >= 4 and parts[0] == "data" and parts[2] == "cfg":
            return "canonical_cfg"
        return "auxiliary_cfg"
    raise ValueError(f"Unsupported FormaLLM public file type: {path}")


def _family(path: Path, *, formalllm_root: Path) -> str | None:
    rel = path.relative_to(formalllm_root.parent)
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == "data":
        return parts[1]
    return None


def _row(path: Path, *, formalllm_root: Path) -> dict[str, Any]:
    category = _classify(path, formalllm_root=formalllm_root)
    return {
        "category": category,
        "family": _family(path, formalllm_root=formalllm_root),
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_manifest(*, formalllm_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repo_root = formalllm_root.parent
    file_paths = sorted([*repo_root.rglob("*.tla"), *repo_root.rglob("*.cfg")])
    rows = [_row(path, formalllm_root=formalllm_root) for path in file_paths]
    category_counts = Counter(str(row["category"]) for row in rows)
    family_counts = Counter(str(row["family"]) for row in rows if row.get("family"))
    summary = {
        "schema": "chattla_formalllm_public_module_manifest_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": _display_path(formalllm_root),
        "formalllm_git_head": _git_head(repo_root),
        "kept_rows": len(rows),
        "category_counts": dict(sorted(category_counts.items())),
        "family_counts_top": [{"family": family, "rows": count} for family, count in family_counts.most_common(20)],
        "repo_tla_files": category_counts["canonical_clean_tla"]
        + category_counts["canonical_variant_tla"]
        + category_counts["auxiliary_tla"],
        "repo_cfg_files": category_counts["canonical_cfg"] + category_counts["auxiliary_cfg"],
        "canonical_tree_tla_files": category_counts["canonical_clean_tla"] + category_counts["canonical_variant_tla"],
        "canonical_clean_tla_files": category_counts["canonical_clean_tla"],
        "canonical_variant_tla_files": category_counts["canonical_variant_tla"],
        "auxiliary_tla_files": category_counts["auxiliary_tla"],
        "canonical_cfg_files": category_counts["canonical_cfg"],
        "auxiliary_cfg_files": category_counts["auxiliary_cfg"],
    }
    return rows, summary


def _write_jsonl_and_summary(*, rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    out.write_text(payload, encoding="utf-8")
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

    rows, summary = build_manifest(formalllm_root=args.formalllm_root)
    report = _write_jsonl_and_summary(rows=rows, summary=summary, out=args.out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
