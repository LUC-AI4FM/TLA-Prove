#!/usr/bin/env python3
"""Inspect local + remote Hugging Face publish readiness for ChatTLA."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
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
    fetch_remote_repo_paths,
    latest_full_benchmark_stats,
    max_published_version,
    next_version_for_publish,
)

DEFAULT_OUT = REPO / "outputs" / "manifests" / "hf_publish_readiness.json"
DEFAULT_BENCHMARK_MAX_AGE_HOURS = 24.0
_AUTO = object()


def _local_gguf_files(gguf_dir: Path) -> list[Path]:
    return sorted(gguf_dir.glob("chattla-20b-*.gguf"))


def _latest_local_gguf(gguf_dir: Path) -> Path | None:
    files = _local_gguf_files(gguf_dir)
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def build_report(
    *,
    repo_id: str = _DEFAULT_REPO,
    gguf_dir: Path = _GGUF_DIR,
    merged_model_dir: Path = REPO / "outputs" / "merged_model",
    state_path: Path = _STATE_PATH,
    readme_template: Path = _README_TEMPLATE,
    benchmark_max_age_hours: float = DEFAULT_BENCHMARK_MAX_AGE_HOURS,
    fetch_remote_paths: Callable[[str], list[str] | None] | None = None,
    benchmark_stats: object = _AUTO,
    now_fn: Callable[[], float] = time.time,
) -> dict[str, Any]:
    state = _load_state() if state_path == _STATE_PATH else json.loads(state_path.read_text(encoding="utf-8"))
    local_last = int(state.get("last_published_version", 0) or 0)
    local_gguf = _latest_local_gguf(gguf_dir)
    local_gguf_files = [_display_path(path) or str(path) for path in _local_gguf_files(gguf_dir)]
    merged_model_config = merged_model_dir / "config.json"
    stats = latest_full_benchmark_stats() if benchmark_stats is _AUTO else benchmark_stats
    benchmark_age_hours = None
    if stats is not None:
        benchmark_age_hours = (now_fn() - float(stats["mtime"])) / 3600.0

    remote_paths = fetch_remote_paths(repo_id) if fetch_remote_paths else None
    remote_last = max_published_version(remote_paths or [])
    next_version, _ = next_version_for_publish(
        local_last=local_last,
        remote_paths=remote_paths,
        version_override=None,
    )

    blockers: list[str] = []
    warnings: list[str] = []
    if local_gguf is None:
        blockers.append("local GGUF artifact missing under outputs/gguf")
    if stats is None:
        blockers.append("no full benchmark CSV found")
    elif benchmark_age_hours is not None and benchmark_age_hours > benchmark_max_age_hours:
        blockers.append(
            f"latest full benchmark is stale at {benchmark_age_hours:.1f}h "
            f"(limit {benchmark_max_age_hours:.1f}h)"
        )
    if not readme_template.is_file():
        blockers.append("outputs/hf_readme/README.md missing")
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
        "ready_to_publish": not blockers,
        "blockers": blockers,
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
            "source_csv": stats["source_csv"],
            "source_path": _display_path(Path(str(stats["source_path"]))),
            "rows": stats["n"],
            "sany": stats["sany"],
            "tlc": stats["tlc"],
            "avg_struct": stats["avg_struct"],
            "age_hours": benchmark_age_hours,
            "fresh_within_hours": benchmark_max_age_hours,
        },
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


def fetch_remote_paths_via_http(repo_id: str) -> list[str] | None:
    url = f"https://huggingface.co/api/models/{repo_id}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
    except Exception:
        return None
    siblings = payload.get("siblings")
    if not isinstance(siblings, list):
        return None
    paths: list[str] = []
    for item in siblings:
        if isinstance(item, dict) and isinstance(item.get("rfilename"), str):
            paths.append(item["rfilename"])
    return paths or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default=_DEFAULT_REPO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--benchmark-max-age-hours", type=float, default=DEFAULT_BENCHMARK_MAX_AGE_HOURS)
    parser.add_argument("--sync-state", action="store_true")
    args = parser.parse_args()

    remote_fetcher = None
    if HfApi is not None:
        api = HfApi()
        remote_fetcher = lambda repo_id: fetch_remote_repo_paths(api, repo_id)
    if remote_fetcher is None:
        remote_fetcher = fetch_remote_paths_via_http

    report = build_report(
        repo_id=args.repo_id,
        benchmark_max_age_hours=args.benchmark_max_age_hours,
        fetch_remote_paths=remote_fetcher,
    )
    if args.sync_state:
        report["state_synced"] = sync_state_to_remote(state_path=_STATE_PATH, report=report)
        if report["state_synced"]:
            report = build_report(
                repo_id=args.repo_id,
                benchmark_max_age_hours=args.benchmark_max_age_hours,
                fetch_remote_paths=remote_fetcher,
            )
            report["state_synced"] = True
        else:
            report["state_synced"] = False

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
