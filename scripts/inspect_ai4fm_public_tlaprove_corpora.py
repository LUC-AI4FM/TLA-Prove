#!/usr/bin/env python3
"""Inspect public TLA-Prove corpora exposed by AI4FM and write a compact JSON report."""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "outputs" / "manifests" / "ai4fm_public_tlaprove_corpora.json"

REPO_NAME = "LUC-AI4FM/TLA-Prove"
API_ROOT = f"https://api.github.com/repos/{REPO_NAME}"
RAW_ROOT = f"https://raw.githubusercontent.com/{REPO_NAME}/main"
TREE_API_TEMPLATE = f"{API_ROOT}/git/trees/{{branch}}?recursive=1"
PROCESSED_DIR = f"{API_ROOT}/contents/data/processed"
RALPH_DIR = f"{API_ROOT}/contents/data/frs_tla_ralph_gen"
DIAMOND_TOPICS_API = f"{API_ROOT}/contents/data/diamond_gen_topics.json"
RALPH_README_API = f"{API_ROOT}/contents/data/frs_tla_ralph_gen/README.md"
DIAMOND_SUMMARY_API = f"{API_ROOT}/contents/data/processed/diamond_sft_v3_summary.json"
BENCHMARK_SUITE_API = f"{API_ROOT}/contents/data/benchmarks/benchmark_suite.json"
BENCHMARK_TO_MODULE_API = f"{API_ROOT}/contents/data/benchmarks/benchmark_to_module.json"
REPO_README_API = f"{API_ROOT}/contents/README.md"


def _load_json_url(url: str) -> Any:
    with urllib.request.urlopen(url) as response:
        return json.load(response)


def _load_text_url(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def _count_jsonl_rows(url: str) -> int:
    with urllib.request.urlopen(url) as response:
        return sum(1 for line in response.read().splitlines() if line.strip())


def _entry_by_name(entries: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for entry in entries:
        if entry.get("name") == name:
            return entry
    raise KeyError(f"Missing entry {name}")


def _corpus_entry(entry: dict[str, Any], row_counts: dict[str, int]) -> dict[str, Any]:
    return {
        "path": entry["path"],
        "html_url": entry["html_url"],
        "download_url": entry["download_url"],
        "sha": entry["sha"],
        "bytes": entry["size"],
        "rows": row_counts[entry["download_url"]],
    }


def _tree_jsonl_entries(tree_listing: list[dict[str, Any]], *, repo_html_url: str, branch: str, row_counts: dict[str, int]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in tree_listing:
        if item.get("type") != "blob":
            continue
        path = str(item.get("path", ""))
        if not path.endswith(".jsonl"):
            continue
        download_url = f"{RAW_ROOT}/{path}"
        entries.append(
            {
                "path": path,
                "html_url": f"{repo_html_url}/blob/{branch}/{path}",
                "download_url": download_url,
                "sha": item["sha"],
                "bytes": item.get("size"),
                "rows": row_counts[download_url],
            }
        )
    return sorted(entries, key=lambda entry: str(entry["path"]))


def _prefix_rollup(entries: list[dict[str, Any]], prefix: str) -> dict[str, int]:
    matching = [entry for entry in entries if str(entry["path"]).startswith(prefix)]
    return {
        "files": len(matching),
        "rows": sum(int(entry["rows"]) for entry in matching),
    }


def _count_non_null_mappings(benchmark_to_module: dict[str, Any]) -> int:
    mappings = benchmark_to_module.get("mappings", [])
    if not isinstance(mappings, list):
        return 0
    count = 0
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        if mapping.get("module_name") is not None:
            count += 1
    return count


def _parse_ralph_readme(readme: str) -> dict[str, int] | None:
    patterns = {
        "carried_over_rows": r"-\s+(\d+)\s+pre-existing rows",
        "new_rows": r"-\s+(\d+)\s+new ralph-gen rows",
        "train_rows": r"-\s+Final splits:\s+(\d+)\s+train",
        "dev_rows": r"-\s+Final splits:\s+\d+\s+train,\s+(\d+)\s+dev",
    }
    extracted: dict[str, int] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, readme)
        if match:
            extracted[key] = int(match.group(1))
    return extracted or None


def build_report(
    *,
    repo: dict[str, str],
    processed_listing: list[dict[str, Any]],
    ralph_listing: list[dict[str, Any]],
    row_counts: dict[str, int],
    diamond_summary: dict[str, Any],
    ralph_readme: str,
    diamond_topics: dict[str, Any],
    diamond_topics_download_url: str,
    ralph_readme_download_url: str,
    all_jsonl_entries: list[dict[str, Any]] | None = None,
    benchmark_suite: list[dict[str, Any]] | None = None,
    benchmark_to_module: dict[str, Any] | None = None,
    repo_readme: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    processed_train = _corpus_entry(_entry_by_name(processed_listing, "train.jsonl"), row_counts)
    processed_eval = _corpus_entry(_entry_by_name(processed_listing, "eval.jsonl"), row_counts)
    diamond_eval_holdout = _corpus_entry(
        _entry_by_name(processed_listing, "diamond_eval_holdout.jsonl"),
        row_counts,
    )
    diamond_sft_v3 = _corpus_entry(_entry_by_name(processed_listing, "diamond_sft_v3.jsonl"), row_counts)
    ralph_train = _corpus_entry(_entry_by_name(ralph_listing, "train.jsonl"), row_counts)
    ralph_dev = _corpus_entry(_entry_by_name(ralph_listing, "dev.jsonl"), row_counts)
    diamond_batches = diamond_topics.get("batches", []) if isinstance(diamond_topics, dict) else []
    topics_total = 0
    for batch in diamond_batches:
        if isinstance(batch, dict):
            topics = batch.get("topics", [])
            if isinstance(topics, list):
                topics_total += len(topics)

    report = {
        "generated_at": generated_at,
        "repo": repo,
        "corpora": {
            "processed_train": processed_train,
            "processed_eval": processed_eval,
            "diamond_eval_holdout": diamond_eval_holdout,
            "diamond_sft_v3": {
                **diamond_sft_v3,
                "summary": diamond_summary,
            },
            "frs_tla_ralph_gen": {
                "train": ralph_train,
                "dev": ralph_dev,
                "readme_url": ralph_readme_download_url,
                "readme_summary": _parse_ralph_readme(ralph_readme),
            },
            "diamond_gen_topics": {
                "download_url": diamond_topics_download_url,
                "doc": diamond_topics.get("_doc") if isinstance(diamond_topics, dict) else None,
                "batches": len(diamond_batches),
                "topics_total": topics_total,
            },
        },
        "aggregate": {
            "total_public_jsonl_rows": sum(
                item["rows"]
                for item in [
                    processed_train,
                    processed_eval,
                    diamond_eval_holdout,
                    diamond_sft_v3,
                    ralph_train,
                    ralph_dev,
                ]
            ),
            "tracked_public_jsonl_files": 6,
            "largest_public_jsonl": {
                "path": diamond_sft_v3["path"],
                "rows": diamond_sft_v3["rows"],
            },
        },
        "recommended_ingest_order": [
            {
                "path": diamond_sft_v3["path"],
                "reason": "largest public SFT corpus; summary reports 713 base rows plus 170 new unique rows, oversampled to 1053 total",
            },
            {
                "path": ralph_train["path"],
                "reason": "public Ralph-generated expansion with 500 train rows and a matching 50-row dev split",
            },
            {
                "path": processed_train["path"],
                "reason": "base public processed train corpus with 713 rows",
            },
            {
                "path": diamond_eval_holdout["path"],
                "reason": "30-row public holdout useful for evaluation alignment",
            },
            {
                "path": "data/diamond_gen_topics.json",
                "reason": "200-topic prompt expansion metadata spanning 10 batches",
            },
        ],
        "public_sources": {
            "repo": repo["html_url"],
            "processed_dir": f"{repo['html_url']}/tree/{repo['default_branch']}/data/processed",
            "ralph_dir": f"{repo['html_url']}/tree/{repo['default_branch']}/data/frs_tla_ralph_gen",
        },
        "notes": [
            "These corpora are committed directly in the public TLA-Prove repository, unlike the larger DVC-backed crawl in tla-dataset-pipeline.",
            "Row totals here are raw public JSONL counts and may include overlap or oversampling across corpora.",
        ],
    }
    tracked_paths = {
        processed_train["path"],
        processed_eval["path"],
        diamond_eval_holdout["path"],
        diamond_sft_v3["path"],
        ralph_train["path"],
        ralph_dev["path"],
    }
    if all_jsonl_entries is not None:
        tracked_rows = int(report["aggregate"]["total_public_jsonl_rows"])
        all_rows = sum(int(entry["rows"]) for entry in all_jsonl_entries)
        extra_entries = [entry for entry in all_jsonl_entries if entry["path"] not in tracked_paths]
        report["aggregate"]["all_public_jsonl_rows"] = all_rows
        report["aggregate"]["all_public_jsonl_files"] = len(all_jsonl_entries)
        report["aggregate"]["additional_public_jsonl_rows_outside_tracked_corpora"] = all_rows - tracked_rows
        report["aggregate"]["additional_public_jsonl_files_outside_tracked_corpora"] = len(extra_entries)
        report["all_public_jsonl_surface"] = {
            "total_rows": all_rows,
            "total_files": len(all_jsonl_entries),
            "tracked_corpora_rows": tracked_rows,
            "tracked_corpora_files": len(tracked_paths),
            "additional_rows_outside_tracked_corpora": all_rows - tracked_rows,
            "additional_files_outside_tracked_corpora": len(extra_entries),
            "by_prefix": {
                "data/processed": _prefix_rollup(all_jsonl_entries, "data/processed/"),
                "data/frs_tla_ralph_gen": _prefix_rollup(all_jsonl_entries, "data/frs_tla_ralph_gen/"),
                "data/toy": _prefix_rollup(all_jsonl_entries, "data/toy/"),
                "outputs/diamond_gen": _prefix_rollup(all_jsonl_entries, "outputs/diamond_gen/"),
            },
            "additional_paths": [entry["path"] for entry in extra_entries],
        }
    if benchmark_suite is not None or benchmark_to_module is not None or repo_readme is not None:
        mappings = benchmark_to_module.get("mappings", []) if isinstance(benchmark_to_module, dict) else []
        holdout_modules = (
            benchmark_to_module.get("holdout_module_names", [])
            if isinstance(benchmark_to_module, dict)
            else []
        )
        suite_items = len(benchmark_suite) if isinstance(benchmark_suite, list) else None
        mapping_items = len(mappings) if isinstance(mappings, list) else None
        non_null_mappings = _count_non_null_mappings(benchmark_to_module or {})
        readme_mentions_30_spec = "30-spec" in repo_readme if isinstance(repo_readme, str) else None
        report["benchmark_surface"] = {
            "benchmark_suite_items": suite_items,
            "benchmark_mapping_items": mapping_items,
            "non_null_module_mappings": non_null_mappings,
            "holdout_module_names": len(holdout_modules) if isinstance(holdout_modules, list) else None,
            "repo_readme_mentions_30_spec_holdout": readme_mentions_30_spec,
        }
        if suite_items is not None and readme_mentions_30_spec and suite_items != 30:
            report["notes"].append(
                "Public TLA-Prove README still mentions a 30-spec held-out suite, but benchmark_suite.json currently contains a different item count."
            )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    repo_meta = _load_json_url(API_ROOT)
    branch = repo_meta["default_branch"]
    branch_meta = _load_json_url(f"{API_ROOT}/branches/{branch}")
    processed_listing = _load_json_url(PROCESSED_DIR)
    ralph_listing = _load_json_url(RALPH_DIR)
    tree_listing = _load_json_url(TREE_API_TEMPLATE.format(branch=branch)).get("tree", [])
    diamond_topics_api = _load_json_url(DIAMOND_TOPICS_API)
    ralph_readme_api = _load_json_url(RALPH_README_API)
    diamond_summary_api = _load_json_url(DIAMOND_SUMMARY_API)
    benchmark_suite_api = _load_json_url(BENCHMARK_SUITE_API)
    benchmark_to_module_api = _load_json_url(BENCHMARK_TO_MODULE_API)
    repo_readme_api = _load_json_url(REPO_README_API)

    row_counts: dict[str, int] = {}
    tracked_download_urls = []
    for entry in processed_listing + ralph_listing:
        if isinstance(entry, dict) and str(entry.get("name", "")).endswith(".jsonl"):
            tracked_download_urls.append(entry["download_url"])
    tree_jsonl_paths = [
        str(item.get("path"))
        for item in tree_listing
        if isinstance(item, dict) and item.get("type") == "blob" and str(item.get("path", "")).endswith(".jsonl")
    ]
    for download_url in sorted({*tracked_download_urls, *(f"{RAW_ROOT}/{path}" for path in tree_jsonl_paths)}):
        row_counts[download_url] = _count_jsonl_rows(download_url)

    repo_info = {
        "nameWithOwner": repo_meta["full_name"],
        "html_url": repo_meta["html_url"],
        "default_branch": branch,
        "head_sha": branch_meta["commit"]["sha"],
    }
    all_jsonl_entries = _tree_jsonl_entries(
        tree_listing,
        repo_html_url=repo_info["html_url"],
        branch=branch,
        row_counts=row_counts,
    )

    report = build_report(
        repo=repo_info,
        processed_listing=processed_listing,
        ralph_listing=ralph_listing,
        row_counts=row_counts,
        diamond_summary=_load_json_url(diamond_summary_api["download_url"]),
        ralph_readme=_load_text_url(ralph_readme_api["download_url"]),
        diamond_topics=_load_json_url(diamond_topics_api["download_url"]),
        diamond_topics_download_url=diamond_topics_api["download_url"],
        ralph_readme_download_url=ralph_readme_api["download_url"],
        all_jsonl_entries=all_jsonl_entries,
        benchmark_suite=_load_json_url(benchmark_suite_api["download_url"]),
        benchmark_to_module=_load_json_url(benchmark_to_module_api["download_url"]),
        repo_readme=_load_text_url(repo_readme_api["download_url"]),
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
