#!/usr/bin/env python3
"""Build a full processed FormaLLM prompt/spec eval corpus from canonical metadata."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.build_sany_tlc_pass_corpus import DEVELOPER_PROMPT, _with_tlc_config

DEFAULT_SOURCE_ROOT = REPO / "data" / "FormaLLM" / "data"
DEFAULT_OUT = REPO / "data" / "processed" / "formalllm_eval_v1.jsonl"


def _load_text(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _pick_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def _comment_candidates(base: Path, family: str, model: str, comments_clean: Any, comments: Any) -> list[Path]:
    candidates: list[Path] = []

    def add_txt(name: str | None) -> None:
        if not name:
            return
        candidates.append(base / "txt" / name)

    add_txt(str(comments_clean) if comments_clean else None)
    add_txt(str(comments) if comments else None)

    aliases: list[str] = []
    if model.startswith("MC_"):
        aliases.append(model.removeprefix("MC_"))
    if model.startswith("MC") and len(model) > 2:
        aliases.append(model[2:])
    aliases.append(family)

    seen: set[str] = set()
    for alias in aliases:
        if not alias or alias in seen:
            continue
        seen.add(alias)
        add_txt(f"{alias}_comments_clean.txt")
        add_txt(f"{alias}_comments.txt")

    candidates.extend(
        [
            base / "README_clean.txt",
            base / "README.txt",
            base / "README.md",
            base / "README",
        ]
    )
    return candidates


def _normalized_final(spec: str, cfg: str | None) -> str:
    body = spec.rstrip() + "\n"
    if cfg and cfg.strip():
        return body + "\n" + cfg.strip() + "\n"
    return _with_tlc_config(spec)


def _record(family: str, entry: dict[str, Any], prompt: str, final: str) -> dict[str, Any]:
    module = str(entry["model"])
    entry_id = str(entry["id"])
    return {
        "_tier": "formalllm_eval",
        "_source": "formalllm_clean_v1",
        "_family": family,
        "_module": module,
        "_prompt_id": f"formalllm/{family}/{entry_id}/{module}",
        "_evidence": {
            "dataset_entry_id": entry_id,
            "family": family,
            "cfg_present": bool(entry.get("cfg")),
            "tla_original": entry.get("tla_original"),
            "tla_clean": entry.get("tla_clean"),
            "comments": entry.get("comments"),
            "comments_clean": entry.get("comments_clean"),
            "cfg": entry.get("cfg"),
        },
        "messages": [
            {"role": "developer", "content": DEVELOPER_PROMPT},
            {
                "role": "user",
                "content": f"Write a TLA+ specification for the following:\n\n{prompt.strip()}\n",
            },
            {
                "role": "assistant",
                "channel": "analysis",
                "content": (
                    f"I'll write module {module} with finite state domains, Init, Next, Spec, "
                    "and TypeOK so it parses with SANY and passes TLC."
                ),
            },
            {"role": "assistant", "channel": "final", "content": final},
        ],
    }


def build_rows(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    skipped_missing_files: list[str] = []

    for meta_path in sorted(source_root.glob("*/*.json")):
        family = meta_path.parent.name
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        data = payload.get("data")
        if not isinstance(data, list):
            continue
        seen_families.add(family)

        for entry in sorted(data, key=lambda item: (str(item.get("id", "")), str(item.get("model", "")))):
            model = str(entry.get("model", ""))
            prompt_path = _pick_existing(
                _comment_candidates(
                    meta_path.parent,
                    family,
                    model,
                    entry.get("comments_clean"),
                    entry.get("comments"),
                )
            )
            spec_path = _pick_existing(
                [
                    meta_path.parent / "tla" / str(entry.get("tla_clean") or ""),
                    meta_path.parent / "tla" / str(entry.get("tla_original") or ""),
                ]
            )
            cfg_path = _pick_existing([meta_path.parent / "cfg" / str(entry.get("cfg") or "")])
            prompt = _load_text(prompt_path)
            spec = _load_text(spec_path)
            cfg = _load_text(cfg_path)
            if not prompt or not spec:
                skipped_missing_files.append(f"{family}:{entry.get('id')}:{entry.get('model')}")
                continue
            rows.append(_record(family, entry, prompt, _normalized_final(spec, cfg)))

    modules = [row["_module"] for row in rows]
    summary = {
        "source_root": str(source_root),
        "families_seen": len(seen_families),
        "rows": len(rows),
        "unique_modules": len(set(modules)),
        "duplicate_modules": sorted(module for module in set(modules) if modules.count(module) > 1),
        "skipped_missing_files": skipped_missing_files,
    }
    return rows, summary


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    final_summary = dict(summary)
    final_summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    final_summary["out"] = str(out.relative_to(REPO)) if out.is_relative_to(REPO) else str(out)
    if final_summary.get("source_root") == str(DEFAULT_SOURCE_ROOT):
        final_summary["source_root"] = str(DEFAULT_SOURCE_ROOT.relative_to(REPO))
    final_summary["jsonl_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_summary["summary"] = (
        str(summary_path.relative_to(REPO)) if summary_path.is_relative_to(REPO) else str(summary_path)
    )
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, summary = build_rows(args.source_root)
    print(json.dumps(write_outputs(rows, summary, args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
