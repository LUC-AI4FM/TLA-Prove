#!/usr/bin/env python3
"""Inspect the public AI4FM dataset surface and write a compact JSON report."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised only if PyYAML is unavailable
    yaml = None


REPO = Path(__file__).resolve().parents[1]
DEFAULT_FORMALLLM_ROOT = REPO / "data" / "FormaLLM" / "data"
DEFAULT_FORMALLLM_INPUT_ROOT = REPO / "data" / "FormaLLM" / "Input"
DEFAULT_FORMALLLM_ARCHITECTURE_DOC = REPO / "data" / "FormaLLM" / "doc" / "ARCHITECTURE.md"
DEFAULT_PIPELINE_REPO = Path("/tmp/LUC-AI4FM-tla-dataset-pipeline")
DEFAULT_OUT = REPO / "outputs" / "manifests" / "ai4fm_public_dataset_surface.json"
ARCHITECTURE_SPEC_COUNT_RE = re.compile(r"Metadata for\s+([0-9][0-9,+]*)\s+specifications")
DEFAULT_FORMALLLM_REPO_URL = "https://github.com/LUC-AI4FM/FormaLLM.git"
DEFAULT_PIPELINE_REPO_URL = "https://github.com/LUC-AI4FM/tla-dataset-pipeline.git"


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


def _remote_head(url: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.SubprocessError:
        return None
    line = completed.stdout.strip()
    return line.split()[0] if line else None


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


def _json_rows(path: Path) -> int | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return len(data)
        return len(payload)
    return None


def _formalllm_split_counts(input_root: Path) -> dict[str, int | None]:
    return {
        "train": _json_rows(input_root / "train.json"),
        "val": _json_rows(input_root / "val.json"),
        "test": _json_rows(input_root / "test.json"),
    }


def _architecture_metadata_claim(path: Path) -> str | None:
    if not path.exists():
        return None
    match = ARCHITECTURE_SPEC_COUNT_RE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def inspect_formalllm(formalllm_root: Path, *, input_root: Path, architecture_doc: Path) -> dict[str, Any]:
    entries, families = _load_family_entries(formalllm_root)
    models = [str(entry.get("model")) for entry in entries if entry.get("model")]
    repo_root = formalllm_root.parent
    tla_files = sorted(formalllm_root.glob("*//tla/*.tla"))
    clean_tla_files = [path for path in tla_files if path.stem.endswith("_clean")]
    repo_tla_files = sorted(repo_root.rglob("*.tla"))
    cfg_files = sorted(formalllm_root.glob("*//cfg/*.cfg"))
    repo_cfg_files = sorted(repo_root.rglob("*.cfg"))
    clean_comment_files = sorted(formalllm_root.glob("*//txt/*_comments_clean.txt"))
    all_comment_files = sorted(formalllm_root.glob("*//txt/*_comments*.txt"))
    split_counts = _formalllm_split_counts(input_root)
    split_total = sum(count for count in split_counts.values() if isinstance(count, int))
    architecture_claim = _architecture_metadata_claim(architecture_doc)
    return {
        "root": str(formalllm_root.relative_to(REPO)) if formalllm_root.is_relative_to(REPO) else formalllm_root.name,
        "git_head": _git_head(repo_root),
        "families": families,
        "canonical_entries": len(entries),
        "unique_models": len(set(models)),
        "tla_files": len(tla_files),
        "clean_tla_files": len(clean_tla_files),
        "nonclean_tla_files": len(tla_files) - len(clean_tla_files),
        "repo_tla_files": len(repo_tla_files),
        "auxiliary_tla_files": len(repo_tla_files) - len(tla_files),
        "cfg_files": len(cfg_files),
        "repo_cfg_files": len(repo_cfg_files),
        "auxiliary_cfg_files": len(repo_cfg_files) - len(cfg_files),
        "clean_comment_files": len(clean_comment_files),
        "comment_files": len(all_comment_files),
        "split_files": {
            "root": str(input_root.relative_to(REPO)) if input_root.is_relative_to(REPO) else str(input_root),
            "counts": split_counts,
            "total": split_total,
        },
        "architecture_doc": {
            "path": str(architecture_doc.relative_to(REPO)) if architecture_doc.is_relative_to(REPO) else str(architecture_doc),
            "metadata_specification_claim": architecture_claim,
        },
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
    seed_repo_config = pipeline_repo / "config" / "seeds" / "repos.yaml"
    query_config = pipeline_repo / "config" / "seeds" / "queries.yaml"
    seed_config_counts: dict[str, int] | None = None
    if yaml is not None and seed_repo_config.exists() and query_config.exists():
        seed_payload = yaml.safe_load(seed_repo_config.read_text(encoding="utf-8")) or {}
        query_payload = yaml.safe_load(query_config.read_text(encoding="utf-8")) or {}
        if isinstance(seed_payload, dict) and isinstance(query_payload, dict):
            repos = seed_payload.get("repos")
            orgs = seed_payload.get("orgs")
            users = seed_payload.get("users")
            queries = query_payload.get("queries")
            seed_config_counts = {
                "repos": len(repos) if isinstance(repos, list) else 0,
                "orgs": len(orgs) if isinstance(orgs, list) else 0,
                "users": len(users) if isinstance(users, list) else 0,
                "queries": len(queries) if isinstance(queries, list) else 0,
            }
    return {
        "repo": pipeline_repo.name,
        "git_head": _git_head(pipeline_repo),
        "dvc_lock": f"{pipeline_repo.name}/dvc.lock" if dvc_lock.exists() else "dvc.lock",
        "dvc_lock_present": dvc_lock.exists(),
        "pull": parsed.get("pull"),
        "parse_input": parsed.get("parse_input"),
        "parse_output": parsed.get("parse_output"),
        "seed_config_counts": seed_config_counts,
    }


def build_report(
    *,
    formalllm_root: Path,
    formalllm_input_root: Path,
    formalllm_architecture_doc: Path,
    pipeline_repo: Path,
    remote_head_resolver: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    formalllm = inspect_formalllm(
        formalllm_root,
        input_root=formalllm_input_root,
        architecture_doc=formalllm_architecture_doc,
    )
    pipeline = inspect_pipeline(pipeline_repo)
    warnings: list[str] = []
    split_total = formalllm.get("split_files", {}).get("total")
    canonical_entries = formalllm.get("canonical_entries")
    if isinstance(split_total, int) and split_total != canonical_entries:
        warnings.append(
            "FormaLLM split-file total does not match canonical_entries."
        )
    clean_tla_files = formalllm.get("clean_tla_files")
    if isinstance(clean_tla_files, int) and clean_tla_files != canonical_entries:
        warnings.append(
            "FormaLLM clean_tla_files count differs from current canonical_entries."
        )
    architecture_claim = formalllm.get("architecture_doc", {}).get("metadata_specification_claim")
    if isinstance(architecture_claim, str) and architecture_claim != str(canonical_entries):
        warnings.append(
            "FormaLLM architecture metadata claim differs from current canonical_entries."
        )
    public_sources = {
        "formalllm_repo": "https://github.com/LUC-AI4FM/FormaLLM",
        "pipeline_repo": "https://github.com/LUC-AI4FM/tla-dataset-pipeline",
        "pipeline_dvc_lock": "https://raw.githubusercontent.com/LUC-AI4FM/tla-dataset-pipeline/main/dvc.lock",
    }
    if remote_head_resolver is not None:
        public_sources["live_remote_heads"] = {
            "formalllm_repo": remote_head_resolver(DEFAULT_FORMALLLM_REPO_URL),
            "pipeline_repo": remote_head_resolver(DEFAULT_PIPELINE_REPO_URL),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "formalllm": formalllm,
        "pipeline": pipeline,
        "warnings": warnings,
        "integration_recommendation": {
            "formalllm_role": "canonical prompt/spec supervised corpus",
            "pipeline_role": "broader public extraction/parsing discovery surface",
            "recommended_next_step": (
                "Use formalllm_eval_v1 for direct supervised/eval work, "
                "build formalllm_public_module_manifest_v1 to audit the broader public FormaLLM file surface, "
                "treat the `_clean.tla` subset inside FormaLLM as the raw-module view of that canonical layer, "
                "inspect ai4fm_public_tlaprove_corpora and build ai4fm_public_tlaprove_import_v1 "
                "for stable public JSONL expansion, build ai4fm_public_seed_file_manifest_v1 "
                "for the committed public GitHub file surface, build "
                "ai4fm_public_seed_tla_modules_v1 for a usable `.tla` module corpus from that lane, "
                "and treat ai4fm_public_discovery_manifest_v1 as the public repo-level expansion lane."
            ),
        },
        "public_sources": public_sources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formalllm-root", type=Path, default=DEFAULT_FORMALLLM_ROOT)
    parser.add_argument("--formalllm-input-root", type=Path, default=DEFAULT_FORMALLLM_INPUT_ROOT)
    parser.add_argument("--formalllm-architecture-doc", type=Path, default=DEFAULT_FORMALLLM_ARCHITECTURE_DOC)
    parser.add_argument("--pipeline-repo", type=Path, default=DEFAULT_PIPELINE_REPO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--include-remote-heads", action="store_true")
    args = parser.parse_args()

    report = build_report(
        formalllm_root=args.formalllm_root,
        formalllm_input_root=args.formalllm_input_root,
        formalllm_architecture_doc=args.formalllm_architecture_doc,
        pipeline_repo=args.pipeline_repo,
        remote_head_resolver=_remote_head if args.include_remote_heads else None,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
