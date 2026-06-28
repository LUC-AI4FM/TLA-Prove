#!/usr/bin/env python3
"""Inspect the public AI4FM dataset surface and write a compact JSON report."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised only if PyYAML is unavailable
    yaml = None


REPO = Path(__file__).resolve().parents[1]
DEFAULT_FORMALLLM_ROOT = REPO / "data" / "FormaLLM" / "data"
DEFAULT_PIPELINE_REPO = Path("/tmp/LUC-AI4FM-tla-dataset-pipeline")
DEFAULT_OUT = REPO / "outputs" / "manifests" / "ai4fm_public_dataset_surface.json"


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


def _load_family_entries(formalllm_root: Path) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    families = 0
    for meta_path in sorted(formalllm_root.glob("*/*.json")):
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        data = payload.get("data")
        if isinstance(data, list):
            families += 1
            entries.extend(item for item in data if isinstance(item, dict))
    return entries, families


def inspect_formalllm(formalllm_root: Path) -> dict[str, Any]:
    entries, families = _load_family_entries(formalllm_root)
    models = [str(entry.get("model")) for entry in entries if entry.get("model")]
    tla_files = sorted(formalllm_root.glob("*//tla/*.tla"))
    cfg_files = sorted(formalllm_root.glob("*//cfg/*.cfg"))
    clean_comment_files = sorted(formalllm_root.glob("*//txt/*_comments_clean.txt"))
    all_comment_files = sorted(formalllm_root.glob("*//txt/*_comments*.txt"))
    repo_root = formalllm_root.parent
    return {
        "root": str(formalllm_root.relative_to(REPO)) if formalllm_root.is_relative_to(REPO) else formalllm_root.name,
        "git_head": _git_head(repo_root),
        "families": families,
        "canonical_entries": len(entries),
        "unique_models": len(set(models)),
        "tla_files": len(tla_files),
        "cfg_files": len(cfg_files),
        "clean_comment_files": len(clean_comment_files),
        "comment_files": len(all_comment_files),
    }


def _stage_slot(stage: dict[str, Any], slot: str, *, source: str | None = None) -> dict[str, Any] | None:
    items = stage.get(slot)
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        if source is None or item.get("path") == source:
            return {
                "path": item.get("path"),
                "size": item.get("size"),
                "nfiles": item.get("nfiles"),
            }
    return None


def _parse_dvc_lock(dvc_lock: Path) -> dict[str, Any]:
    text = dvc_lock.read_text(encoding="utf-8")
    if yaml is not None:
        payload = yaml.safe_load(text) or {}
        stages = payload.get("stages", {}) if isinstance(payload, dict) else {}
        if isinstance(stages, dict):
            pull = stages.get("pull", {})
            parse = stages.get("parse", {})
            return {
                "pull": _stage_slot(pull if isinstance(pull, dict) else {}, "outs", source="data/raw"),
                "parse_input": _stage_slot(parse if isinstance(parse, dict) else {}, "deps", source="data/raw"),
                "parse_output": _stage_slot(parse if isinstance(parse, dict) else {}, "outs", source="data/parsed"),
            }

    current_stage: str | None = None
    current_slot: str | None = None
    slots: dict[str, list[dict[str, Any]]] = {}
    current_item: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("  ") and line.strip().endswith(":") and not line.strip().startswith("-"):
            current_stage = line.strip()[:-1]
            current_slot = None
            slots.setdefault(current_stage, [])
            current_item = None
        elif current_stage and line.startswith("    ") and line.strip() in {"deps:", "outs:"}:
            current_slot = line.strip()[:-1]
            current_item = None
        elif current_stage and current_slot and line.startswith("    - "):
            current_item = {}
            slots[current_stage].append({"slot": current_slot, "item": current_item})
            key, _, value = line.strip()[2:].partition(":")
            current_item[key.strip()] = value.strip()
        elif current_stage and current_slot and current_item is not None and line.startswith("      "):
            key, _, value = line.strip().partition(":")
            current_item[key.strip()] = value.strip()

    def _find(stage_name: str, slot_name: str, path_name: str) -> dict[str, Any] | None:
        for wrapped in slots.get(stage_name, []):
            if wrapped.get("slot") != slot_name:
                continue
            item = wrapped.get("item") or {}
            if item.get("path") == path_name:
                return {
                    "path": item.get("path"),
                    "size": int(item["size"]) if str(item.get("size", "")).isdigit() else item.get("size"),
                    "nfiles": int(item["nfiles"]) if str(item.get("nfiles", "")).isdigit() else item.get("nfiles"),
                }
        return None

    return {
        "pull": _find("pull", "outs", "data/raw"),
        "parse_input": _find("parse", "deps", "data/raw"),
        "parse_output": _find("parse", "outs", "data/parsed"),
    }


def inspect_pipeline(pipeline_repo: Path) -> dict[str, Any]:
    dvc_lock = pipeline_repo / "dvc.lock"
    parsed = _parse_dvc_lock(dvc_lock) if dvc_lock.exists() else {}
    return {
        "repo": pipeline_repo.name,
        "git_head": _git_head(pipeline_repo),
        "dvc_lock": f"{pipeline_repo.name}/dvc.lock" if dvc_lock.exists() else "dvc.lock",
        "dvc_lock_present": dvc_lock.exists(),
        "pull": parsed.get("pull"),
        "parse_input": parsed.get("parse_input"),
        "parse_output": parsed.get("parse_output"),
    }


def build_report(*, formalllm_root: Path, pipeline_repo: Path) -> dict[str, Any]:
    formalllm = inspect_formalllm(formalllm_root)
    pipeline = inspect_pipeline(pipeline_repo)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "formalllm": formalllm,
        "pipeline": pipeline,
        "integration_recommendation": {
            "formalllm_role": "canonical prompt/spec supervised corpus",
            "pipeline_role": "broader public extraction/parsing discovery surface",
            "recommended_next_step": (
                "Use formalllm_eval_v1 for direct supervised/eval work, "
                "inspect ai4fm_public_tlaprove_corpora and build ai4fm_public_tlaprove_import_v1 "
                "for stable public JSONL expansion, "
                "and treat ai4fm_public_discovery_manifest_v1 as the public repo-level expansion lane."
            ),
        },
        "public_sources": {
            "formalllm_repo": "https://github.com/LUC-AI4FM/FormaLLM",
            "pipeline_repo": "https://github.com/LUC-AI4FM/tla-dataset-pipeline",
            "pipeline_dvc_lock": "https://raw.githubusercontent.com/LUC-AI4FM/tla-dataset-pipeline/main/dvc.lock",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formalllm-root", type=Path, default=DEFAULT_FORMALLLM_ROOT)
    parser.add_argument("--pipeline-repo", type=Path, default=DEFAULT_PIPELINE_REPO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report(formalllm_root=args.formalllm_root, pipeline_repo=args.pipeline_repo)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
