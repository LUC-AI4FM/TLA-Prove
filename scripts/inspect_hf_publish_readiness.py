#!/usr/bin/env python3
"""Inspect local + remote Hugging Face publish readiness for ChatTLA."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from huggingface_hub import HfApi  # type: ignore
except ImportError:  # pragma: no cover
    HfApi = None


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.training.publish_hf import (
    _DEFAULT_REPO,
    _GGUF_DIR,
    _README_TEMPLATE,
    _STATE_PATH,
    _load_state,
    _save_state,
    default_benchmark_model,
    fetch_remote_repo_paths,
    fetch_remote_paths_via_http,
    latest_full_benchmark_stats,
    max_published_version,
    next_version_for_publish,
    publish_readiness_blockers,
)

DEFAULT_OUT = REPO / "outputs" / "manifests" / "hf_publish_readiness.json"
DEFAULT_BENCHMARK_MAX_AGE_HOURS = 24.0
DEFAULT_GGUF_SEARCH_DIRS = (
    _GGUF_DIR,
    REPO / "outputs" / "gguf_fc128_best",
)
_AUTO = object()
_CORE_COMPONENT_FIELDS = (
    "init_present",
    "next_present",
    "init_level_ok",
    "next_level_ok",
    "invariants_declared",
    "tlc_depth1_ok",
)
_RED_FLAG_PATTERNS = {
    "obvious_placeholder_rows": re.compile(r"\.\.\.|placeholder|omitted|todo|etc\.", re.IGNORECASE),
    "duplicate_variables_rows": re.compile(r"\bVARIABLES\b[^\n]*\b(\w+)\b[^\n]*\b\1\b"),
    "pseudo_tla_token_rows": re.compile(
        r"\bforall\b|\bexists\b|\bwhere\b|\bconstdef\b|#=|subsete\[\?\]|RemoveAt\(|SeqFromList|SeqSubseq",
        re.IGNORECASE,
    ),
}


def build_claim_status(
    *,
    blockers: list[str],
    stats: dict[str, Any] | None,
) -> dict[str, Any]:
    if stats is None:
        return {
            "supports_public_benchmark_100_percent_claim": False,
            "reason": "No full benchmark CSV is available, so a public benchmark correctness claim is unsupported.",
        }

    rows = int(stats.get("n", 0) or 0)
    sany = int(stats.get("sany", 0) or 0)
    tlc = int(stats.get("tlc", 0) or 0)
    if rows > 0 and not blockers and sany == rows and tlc == rows:
        return {
            "supports_public_benchmark_100_percent_claim": True,
            "reason": f"Latest full benchmark reaches {sany}/{rows} SANY and {tlc}/{rows} TLC, so the public benchmark claim is supported.",
        }
    return {
        "supports_public_benchmark_100_percent_claim": False,
        "reason": f"Latest full benchmark reaches only {sany}/{rows} SANY and {tlc}/{rows} TLC, so the public benchmark claim is unsupported.",
    }


def default_out_path_for_benchmark_model(benchmark_model: str | None) -> Path:
    canonical_model = default_benchmark_model()
    if not benchmark_model or benchmark_model == canonical_model:
        return DEFAULT_OUT
    safe_model = re.sub(r"[^A-Za-z0-9]+", "_", benchmark_model).strip("_").lower()
    if not safe_model:
        return DEFAULT_OUT
    return DEFAULT_OUT.parent / f"{DEFAULT_OUT.stem}.{safe_model}{DEFAULT_OUT.suffix}"


def _local_gguf_files(*gguf_dirs: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for gguf_dir in gguf_dirs:
        for path in sorted(gguf_dir.glob("chattla-20b-*.gguf")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    return files


def _latest_local_gguf(*gguf_dirs: Path) -> Path | None:
    files = _local_gguf_files(*gguf_dirs)
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _load_selected_benchmark_rows(source_path: Path, benchmark_model: str | None) -> list[dict[str, str]]:
    with source_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if benchmark_model is None:
        return rows
    return [row for row in rows if str(row.get("model", "")).strip() == benchmark_model]


def _is_truthy_csv(value: object) -> bool:
    return str(value).strip() in ("1", "True", "true", "yes")


def build_failure_surface(source_path: Path, *, benchmark_model: str | None = None) -> dict[str, Any]:
    rows = _load_selected_benchmark_rows(source_path, benchmark_model)
    red_flag_counts = {name: 0 for name in _RED_FLAG_PATTERNS}
    component_failures = {f"missing_{field}_rows": 0 for field in _CORE_COMPONENT_FIELDS}
    rows_with_any_core_component = 0
    rows_with_all_core_components = 0
    rows_with_no_core_components = 0
    plan_used_rows = 0
    sample_no_core_components: list[str] = []
    sample_placeholder_rows: list[str] = []

    for row in rows:
        benchmark_id = str(row.get("benchmark_id", "")).strip()
        component_truths = {field: _is_truthy_csv(row.get(field, "")) for field in _CORE_COMPONENT_FIELDS}
        component_true_count = sum(1 for ok in component_truths.values() if ok)
        if component_true_count > 0:
            rows_with_any_core_component += 1
        if component_true_count == len(_CORE_COMPONENT_FIELDS):
            rows_with_all_core_components += 1
        if component_true_count == 0:
            rows_with_no_core_components += 1
            if benchmark_id and len(sample_no_core_components) < 5:
                sample_no_core_components.append(benchmark_id)
        for field, ok in component_truths.items():
            if not ok:
                component_failures[f"missing_{field}_rows"] += 1

        if _is_truthy_csv(row.get("plan_used", "")):
            plan_used_rows += 1

        spec = str(row.get("generated_spec", ""))
        row_has_placeholder = False
        for name, pattern in _RED_FLAG_PATTERNS.items():
            if pattern.search(spec):
                red_flag_counts[name] += 1
                if name == "obvious_placeholder_rows":
                    row_has_placeholder = True
        if row_has_placeholder and benchmark_id and len(sample_placeholder_rows) < 5:
            sample_placeholder_rows.append(benchmark_id)

    return {
        "rows": len(rows),
        "aggregate": {
            "rows_with_any_core_component": rows_with_any_core_component,
            "rows_with_all_core_components": rows_with_all_core_components,
            "rows_with_no_core_components": rows_with_no_core_components,
        },
        "core_component_failures": component_failures,
        "red_flags": red_flag_counts,
        "planning": {
            "plan_used_rows": plan_used_rows,
            "plan_unused_rows": max(0, len(rows) - plan_used_rows),
        },
        "sample_benchmark_ids": {
            "no_core_components": sample_no_core_components,
            "obvious_placeholder_rows": sample_placeholder_rows,
        },
    }


def build_report(
    *,
    repo_id: str = _DEFAULT_REPO,
    gguf_dir: Path = _GGUF_DIR,
    gguf_search_dirs: tuple[Path, ...] = DEFAULT_GGUF_SEARCH_DIRS,
    merged_model_dir: Path = REPO / "outputs" / "merged_model",
    state_path: Path = _STATE_PATH,
    readme_template: Path = _README_TEMPLATE,
    benchmark_max_age_hours: float = DEFAULT_BENCHMARK_MAX_AGE_HOURS,
    benchmark_model: str | None = None,
    fetch_remote_paths: Callable[[str], list[str] | None] | None = None,
    benchmark_stats: object = _AUTO,
    now_fn: Callable[[], float] = time.time,
) -> dict[str, Any]:
    state = _load_state() if state_path == _STATE_PATH else json.loads(state_path.read_text(encoding="utf-8"))
    local_last = int(state.get("last_published_version", 0) or 0)
    search_dirs = tuple(dict.fromkeys(gguf_search_dirs))
    local_gguf = _latest_local_gguf(*search_dirs)
    local_gguf_files = [_display_path(path) or str(path) for path in _local_gguf_files(*search_dirs)]
    merged_model_config = merged_model_dir / "config.json"
    if benchmark_stats is _AUTO:
        stats = (
            latest_full_benchmark_stats()
            if benchmark_model is None
            else latest_full_benchmark_stats(benchmark_model=benchmark_model)
        )
    else:
        stats = benchmark_stats
    benchmark_age_hours = None
    if stats is not None:
        benchmark_age_hours = (now_fn() - float(stats["mtime"])) / 3600.0
    failure_surface = None
    if stats is not None:
        try:
            failure_surface = build_failure_surface(
                Path(str(stats["source_path"])),
                benchmark_model=benchmark_model,
            )
        except (OSError, csv.Error):
            failure_surface = None

    remote_paths = fetch_remote_paths(repo_id) if fetch_remote_paths else None
    remote_last = max_published_version(remote_paths or [])
    next_version, _ = next_version_for_publish(
        local_last=local_last,
        remote_paths=remote_paths,
        version_override=None,
    )

    warnings: list[str] = []
    blockers = publish_readiness_blockers(
        gguf_present=local_gguf is not None,
        readme_present=readme_template.is_file(),
        stats=stats,
        benchmark_max_age_hours=benchmark_max_age_hours,
        now=now_fn(),
    )
    claim_status = build_claim_status(blockers=blockers, stats=stats)
    if remote_last is not None and remote_last > local_last:
        warnings.append(
            f"local publish state v{local_last} lags remote GGUF state v{remote_last}"
        )
    note = state.get("note")
    if isinstance(note, str) and "v12" in note and local_last >= 12:
        warnings.append("hf_publish_state note is stale relative to last_published_version")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_id": repo_id,
        "benchmark_model": benchmark_model,
        "ready_to_publish": not blockers,
        "blockers": blockers,
        "claim_status": claim_status,
        "warnings": warnings,
        "state": {
            "path": _display_path(state_path),
            "last_published_version": local_last,
            "last_repo": state.get("last_repo"),
            "last_gguf_path_in_repo": state.get("last_gguf_path_in_repo"),
            "last_cycle_id": state.get("last_cycle_id"),
            "note": note,
        },
        "local": {
            "gguf_dir": _display_path(gguf_dir),
            "gguf_search_dirs": [_display_path(path) for path in search_dirs],
            "gguf_files": local_gguf_files,
            "latest_gguf": _display_path(local_gguf),
            "merged_model_dir": _display_path(merged_model_dir),
            "merged_model_config_present": merged_model_config.is_file(),
            "readme_template": _display_path(readme_template),
            "readme_template_present": readme_template.is_file(),
        },
        "benchmark": None
        if stats is None
        else {
            "model": stats.get("model", benchmark_model),
            "source_csv": stats["source_csv"],
            "source_path": _display_path(Path(str(stats["source_path"]))),
            "rows": stats["n"],
            "sany": stats["sany"],
            "tlc": stats["tlc"],
            "avg_struct": stats["avg_struct"],
            "age_hours": benchmark_age_hours,
            "fresh_within_hours": benchmark_max_age_hours,
            "execution": stats.get("execution"),
        },
        "failure_surface": failure_surface,
        "remote": {
            "gguf_files": [path for path in (remote_paths or []) if path.startswith("gguf/")],
            "latest_published_version": remote_last,
        },
        "next_publish_version": next_version,
    }


def sync_state_to_remote(*, state_path: Path, report: dict[str, Any]) -> bool:
    remote_last = report.get("remote", {}).get("latest_published_version")
    if not isinstance(remote_last, int):
        return False
    state = _load_state() if state_path == _STATE_PATH else json.loads(state_path.read_text(encoding="utf-8"))
    local_last = int(state.get("last_published_version", 0) or 0)
    if remote_last <= local_last:
        return False
    state["last_published_version"] = remote_last
    gguf_files = report.get("remote", {}).get("gguf_files") or []
    target = f"gguf/chattla-20b-v{remote_last}-Q8_0.gguf"
    if target in gguf_files:
        state["last_gguf_path_in_repo"] = target
    state["last_repo"] = report.get("repo_id")
    state["note"] = (
        f"State aligned to remote Hugging Face publish surface on "
        f"{datetime.now(timezone.utc).date().isoformat()}."
    )
    if state_path == _STATE_PATH:
        _save_state(state)
    else:
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return True
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default=_DEFAULT_REPO)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--benchmark-max-age-hours", type=float, default=DEFAULT_BENCHMARK_MAX_AGE_HOURS)
    parser.add_argument("--benchmark-model", default=default_benchmark_model())
    parser.add_argument("--sync-state", action="store_true")
    args = parser.parse_args()

    remote_fetcher = None
    if HfApi is not None:
        api = HfApi()
        remote_fetcher = lambda repo_id: fetch_remote_repo_paths(api, repo_id)
    if remote_fetcher is None:
        remote_fetcher = fetch_remote_paths_via_http

    out_path = args.out or default_out_path_for_benchmark_model(args.benchmark_model)
    report = build_report(
        repo_id=args.repo_id,
        benchmark_max_age_hours=args.benchmark_max_age_hours,
        benchmark_model=args.benchmark_model,
        fetch_remote_paths=remote_fetcher,
    )
    if args.sync_state:
        report["state_synced"] = sync_state_to_remote(state_path=_STATE_PATH, report=report)
        if report["state_synced"]:
            report = build_report(
                repo_id=args.repo_id,
                benchmark_max_age_hours=args.benchmark_max_age_hours,
                benchmark_model=args.benchmark_model,
                fetch_remote_paths=remote_fetcher,
            )
            report["state_synced"] = True
        else:
            report["state_synced"] = False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
