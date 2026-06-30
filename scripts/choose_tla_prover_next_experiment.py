#!/usr/bin/env python3
"""Choose the next local TLA prover action from tracked decision artifacts."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "outputs" / "manifests" / "tla_prover_next_experiment.json"
REMOTE_DECISION_PATH = "outputs/manifests/tla_prover_remote_decision.json"
EXPERIMENT_MATRIX_PATH = "outputs/manifests/tla_prover_corpus_experiment_matrix.json"
HF_READINESS_PATH = "outputs/manifests/hf_publish_readiness.json"
HF_READINESS_FC128BEST_PATH = "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json"
REPAIR_SUMMARY_PATH = "data/processed/tla_prover_repair_train_v1.summary.json"
BENCHMARK_REPAIR_SUMMARY_PATH = "data/processed/benchmark_repair_pairs_fc128best.summary.json"
FAILURE_ANALYSIS_PATH = "outputs/manifests/tla_prover_full_dataset_failure_analysis.json"
FULL_DATASET_REPAIR_QUEUE_SUMMARY_PATH = "outputs/manifests/tla_prover_full_dataset_repair_queue.summary.json"
FULL_DATASET_REPAIR_EVIDENCE_SUMMARY_PATH = "outputs/manifests/tla_prover_full_dataset_repair_evidence.summary.json"
PATCH_WORKLIST_PATH = "outputs/manifests/tla_prover_patch_worklist.json"
PATCH_PACKETS_PATH = "outputs/manifests/tla_prover_patch_packets.json"
FULL_DATASET_VALIDATED_REPAIR_PAIRS_SUMMARY_PATH = "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.summary.json"
FULL_DATASET_HARNESS_REPAIR_PAIRS_SUMMARY_PATH = "data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.summary.json"
PUBLISHED_PROOF_SUMMARY_PATH = "outputs/autoprover/tlaps_verify_published_161016/summary.json"
LOCAL_REPAIR_PLAN_PATH = "outputs/manifests/tla_prover_local_repair_plan.json"
LOCAL_REPAIR_RUNTIME_IMPORT_TIMEOUT_S = 10
LOCAL_REPAIR_STATUS_COMMAND = (
    "python3 scripts/train_tla_prover_repair_local.py --preflight --dry-run "
    f"--runtime-import-timeout-s {LOCAL_REPAIR_RUNTIME_IMPORT_TIMEOUT_S} "
    "--out outputs/manifests/tla_prover_local_repair_plan.json"
)
VALID_INTENTS = ("auto", "repair", "sft-preflight", "publish")
CORPUS_EXPANSION_SEQUENCE = ("default", "expanded", "full-public")
DEFAULT_REPAIR_CORPUS_PROFILE = "default"
PROOF_REPAIR_PRIMARY_PROFILE = "proof_repair_primary"
TIMEOUT_ERROR_RE = re.compile(r"timed out after (?P<seconds>\d+(?:\.\d+)?)s", re.IGNORECASE)

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.doctor_tla_prover_handoff import decide_action as decide_handoff_action
from scripts.status_tla_prover_handoff import build_status as build_handoff_status
from scripts.status_tla_prover_handoff import compact_status as compact_handoff_status


def _compact_bootstrap_recommendation(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {
        key: value.get(key)
        for key in ("reason", "command", "message")
        if key in value
    }
    return compact or None


def _read_json(repo: Path, rel_path: str) -> dict[str, Any]:
    return json.loads((repo / rel_path).read_text(encoding="utf-8"))


def _read_optional_json(repo: Path, rel_path: str) -> dict[str, Any] | None:
    path = repo / rel_path
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _observed_runtime_timeout_s(payload: dict[str, Any], runtime_dependencies: dict[str, Any]) -> float | None:
    raw_timeout = payload.get("runtime_import_timeout_s")
    if raw_timeout is not None:
        try:
            return float(raw_timeout)
        except (TypeError, ValueError):
            pass
    observed: list[float] = []
    for entry in list(runtime_dependencies.get("missing") or []):
        match = TIMEOUT_ERROR_RE.search(str(entry.get("error") or ""))
        if match:
            observed.append(float(match.group("seconds")))
    return max(observed) if observed else None


def _decision_blocks_sft(decision: dict[str, Any]) -> bool:
    verdict = str(decision.get("verdict", "")).strip().lower()
    full_dataset_verdict = str(decision.get("full_dataset_verdict", "")).strip().lower()
    next_action = str(decision.get("next_action", "")).strip().lower()
    full_dataset_next_action = str(decision.get("full_dataset_next_action", "")).strip().lower()
    return (
        verdict == "patch"
        or full_dataset_verdict == "patch"
        or "do not launch sft" in next_action
        or "do not launch sft" in full_dataset_next_action
    )


def _publish_choice(
    readiness: dict[str, Any],
    readiness_fc128best: dict[str, Any],
) -> tuple[str | None, str | None]:
    if bool(readiness.get("ready_to_publish")):
        return "chattla:20b", "python3 -m src.training.publish_hf --dry-run"
    if bool(readiness_fc128best.get("ready_to_publish")):
        return (
            "chattla:20b-fc128best",
            "python3 -m src.training.publish_hf --dry-run --benchmark-model chattla:20b-fc128best",
        )
    return None, None


def _preferred_sft_lane(matrix: dict[str, Any]) -> str | None:
    lanes = dict(matrix.get("lanes") or {})
    for alias in ("expanded", "default", "full-public"):
        lane = lanes.get(alias)
        if lane and bool(lane.get("trainable")):
            return alias
    return None


def _comparison_plan_command(*, baseline: str, candidate: str, mode: str) -> dict[str, Any]:
    comparison_id = f"{baseline}-vs-{candidate}-{mode}"
    return {
        "comparison_id": comparison_id,
        "baseline": baseline,
        "candidate": candidate,
        "mode": mode,
        "command": (
            "python3 scripts/build_tla_prover_lane_comparison_plan.py "
            f"--baseline {baseline} --candidate {candidate} --mode {mode} "
            f"--out outputs/manifests/tla_prover_lane_comparison_plan.{comparison_id}.json"
        ),
    }


def _corpus_expansion_status(matrix: dict[str, Any]) -> dict[str, Any]:
    lanes = dict(matrix.get("lanes") or {})
    status: dict[str, Any] = {
        "recommended_sequence": [alias for alias in CORPUS_EXPANSION_SEQUENCE if alias in lanes],
        "lanes": {},
        "public_ai4fm_scope": dict(matrix.get("public_ai4fm_scope") or {}),
    }
    for alias in CORPUS_EXPANSION_SEQUENCE:
        lane = lanes.get(alias)
        if not isinstance(lane, dict):
            continue
        status["lanes"][alias] = {
            "rows": lane.get("rows"),
            "trainable": bool(lane.get("trainable")),
            "path": lane.get("path"),
            "intended_role": lane.get("intended_role"),
        }
    return status


def _comparison_plan_commands(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    lanes = dict(matrix.get("lanes") or {})
    commands: list[dict[str, Any]] = []
    pairs = (
        ("default", "expanded"),
        ("expanded", "full-public"),
    )
    for baseline, candidate in pairs:
        baseline_lane = lanes.get(baseline)
        candidate_lane = lanes.get(candidate)
        if not isinstance(baseline_lane, dict) or not isinstance(candidate_lane, dict):
            continue
        if not bool(baseline_lane.get("trainable")) or not bool(candidate_lane.get("trainable")):
            continue
        row_delta = None
        try:
            row_delta = int(candidate_lane.get("rows")) - int(baseline_lane.get("rows"))
        except (TypeError, ValueError):
            row_delta = None
        item = _comparison_plan_command(baseline=baseline, candidate=candidate, mode="local")
        item["row_delta"] = row_delta
        commands.append(item)
    return commands


def _repair_expansion_status(matrix: dict[str, Any]) -> dict[str, Any] | None:
    status = matrix.get("repair_corpus_status")
    if not isinstance(status, dict):
        return None
    return {
        "rows": status.get("rows"),
        "health": dict(status.get("health") or {}),
        "missing_sources": list(status.get("missing_sources") or []),
        "sources": dict(status.get("sources") or {}),
        "comparisons": dict(status.get("comparisons") or {}),
    }


def _published_proof_status(summary: dict[str, Any] | None) -> dict[str, Any]:
    if summary is None:
        return {
            "present": False,
            "modules": None,
            "raw_proved": None,
            "raw_total": None,
            "all_modules_proved": None,
            "matches_expected_summary": None,
            "supports_published_proof_claim": False,
        }
    supports_claim = (
        bool(summary.get("all_modules_proved"))
        and summary.get("matches_expected_summary") is not False
        and summary.get("raw_proved") == summary.get("raw_total")
        and summary.get("raw_total") is not None
    )
    return {
        "present": True,
        "modules": summary.get("modules"),
        "raw_proved": summary.get("raw_proved"),
        "raw_total": summary.get("raw_total"),
        "all_modules_proved": summary.get("all_modules_proved"),
        "matches_expected_summary": summary.get("matches_expected_summary"),
        "supports_published_proof_claim": supports_claim,
    }


def _supports_public_benchmark_100_percent_claim(readiness: dict[str, Any]) -> bool:
    benchmark = dict(readiness.get("benchmark") or {})
    rows = benchmark.get("rows")
    sany = benchmark.get("sany")
    tlc = benchmark.get("tlc")
    return (
        bool(readiness.get("ready_to_publish"))
        and isinstance(rows, int)
        and rows > 0
        and sany == rows
        and tlc == rows
    )


def _public_benchmark_correctness_status(
    readiness: dict[str, Any],
    readiness_fc128best: dict[str, Any],
) -> dict[str, Any]:
    candidates = [readiness, readiness_fc128best]
    supported_model = next(
        (candidate.get("benchmark_model") for candidate in candidates if _supports_public_benchmark_100_percent_claim(candidate)),
        None,
    )
    return {
        "supports_public_benchmark_100_percent_claim": supported_model is not None,
        "best_available_model": supported_model,
        "default_model": {
            "benchmark_model": readiness.get("benchmark_model"),
            "ready_to_publish": readiness.get("ready_to_publish"),
            "rows": dict(readiness.get("benchmark") or {}).get("rows"),
            "sany": dict(readiness.get("benchmark") or {}).get("sany"),
            "tlc": dict(readiness.get("benchmark") or {}).get("tlc"),
        },
        "fc128best_model": {
            "benchmark_model": readiness_fc128best.get("benchmark_model"),
            "ready_to_publish": readiness_fc128best.get("ready_to_publish"),
            "rows": dict(readiness_fc128best.get("benchmark") or {}).get("rows"),
            "sany": dict(readiness_fc128best.get("benchmark") or {}).get("sany"),
            "tlc": dict(readiness_fc128best.get("benchmark") or {}).get("tlc"),
        },
    }


def _repair_profile_args(repair_corpus_profile: str) -> str:
    if repair_corpus_profile == DEFAULT_REPAIR_CORPUS_PROFILE:
        return ""
    return f" --repair-corpus-profile {repair_corpus_profile}"


def _repair_corpus_builder_profile_args(repair_corpus_profile: str) -> str:
    if repair_corpus_profile == DEFAULT_REPAIR_CORPUS_PROFILE:
        return ""
    return f" --profile {repair_corpus_profile}"


def _repair_command(repair_corpus_profile: str = DEFAULT_REPAIR_CORPUS_PROFILE) -> str:
    return (
        "python3 scripts/train_tla_prover_repair_local.py --refresh-corpus"
        f"{_repair_profile_args(repair_corpus_profile)}"
    )


def _repair_refresh_command(repair_corpus_profile: str = DEFAULT_REPAIR_CORPUS_PROFILE) -> str:
    return (
        "python3 scripts/build_tla_prover_full_dataset_repair_queue.py "
        "&& python3 scripts/build_tla_prover_full_dataset_repair_evidence.py "
        "&& python3 scripts/build_tla_prover_full_dataset_validated_repair_pairs.py "
        "--allowed-tier gold --allowed-tier silver "
        "&& python3 scripts/build_tla_prover_full_dataset_validated_repair_pairs.py "
        "--allowed-tier gold --allowed-tier silver --include-harness "
        "--only-bucket skip_harness_repair "
        "--out data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.jsonl "
        "&& python3 scripts/build_tla_prover_repair_corpus.py"
        f"{_repair_corpus_builder_profile_args(repair_corpus_profile)}"
    )


def _repair_local_preflight_command(repair_corpus_profile: str = DEFAULT_REPAIR_CORPUS_PROFILE) -> str:
    profile_args = _repair_profile_args(repair_corpus_profile)
    return (
        "python3 scripts/train_tla_prover_repair_local.py --preflight --refresh-corpus"
        f"{profile_args} "
        f"--runtime-import-timeout-s {LOCAL_REPAIR_RUNTIME_IMPORT_TIMEOUT_S}"
    )


def _patch_worklist_command() -> str:
    return "python3 scripts/build_tla_prover_patch_worklist.py"


def _patch_packets_command() -> str:
    return "python3 scripts/build_tla_prover_patch_packets.py"


def _patch_packets_summary(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    return {
        "primary_focus": dict(payload.get("primary_focus") or {}),
        "counts_by_bucket": dict(payload.get("counts_by_bucket") or {}),
        "recommended_next_step": payload.get("recommended_next_step"),
    }


def _repair_local_train_command(repair_corpus_profile: str = DEFAULT_REPAIR_CORPUS_PROFILE) -> str:
    return (
        "python3 scripts/train_tla_prover_repair_local.py --refresh-corpus"
        f"{_repair_profile_args(repair_corpus_profile)}"
    )


def _recommended_repair_corpus_profile(
    patch_packets: dict[str, Any] | None,
    patch_worklist: dict[str, Any] | None,
) -> str:
    primary_focus = dict((patch_packets or {}).get("primary_focus") or {})
    if not primary_focus:
        primary_focus = dict((patch_worklist or {}).get("primary_focus") or {})
    if str(primary_focus.get("repair_bucket") or "").strip() == "proof_repair":
        return PROOF_REPAIR_PRIMARY_PROFILE
    return DEFAULT_REPAIR_CORPUS_PROFILE


def _full_dataset_repair_queue_command() -> str:
    return "python3 scripts/build_tla_prover_full_dataset_repair_queue.py"


def _full_dataset_repair_evidence_command() -> str:
    return "python3 scripts/build_tla_prover_full_dataset_repair_evidence.py"


def _full_dataset_validated_repair_pairs_command() -> str:
    return (
        "python3 scripts/build_tla_prover_full_dataset_validated_repair_pairs.py "
        "--allowed-tier gold --allowed-tier silver"
    )


def _full_dataset_harness_repair_pairs_command() -> str:
    return (
        "python3 scripts/build_tla_prover_full_dataset_validated_repair_pairs.py "
        "--allowed-tier gold --allowed-tier silver --include-harness "
        "--only-bucket skip_harness_repair "
        "--out data/processed/tla_prover_full_dataset_harness_repair_pairs_v1.jsonl"
    )


def _sft_command(lane: str) -> str:
    return (
        "scripts/sync_sophia_and_submit_known18.sh "
        f"--sft-corpus {lane} --submit-sft-preflight"
    )


def _local_sft_command(lane: str) -> str:
    return (
        "python3 scripts/train_tla_prover_local.py "
        f"--sft-corpus {lane}"
    )


def _benchmark_gold_coverage(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    gold_coverage = dict(summary.get("gold_coverage") or {})
    return {
        "failed_rows_seen": summary.get("failed_rows_seen"),
        "covered_failed_rows": gold_coverage.get("covered_failed_rows"),
        "missing_gold_benchmark_ids": gold_coverage.get("missing_gold_benchmark_ids", []),
    }


def _failure_priority(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    action_bucket_counts = {
        str(bucket): int(count)
        for bucket, count in dict(summary.get("action_bucket_counts") or {}).items()
    }
    actionable_buckets = {
        "proof_repair",
        "inductiveness_repair",
        "tlc_repair",
        "skip_harness_repair",
    }
    top_action_buckets = [
        {"bucket": bucket, "count": count}
        for bucket, count in sorted(
            (
                (bucket, count)
                for bucket, count in action_bucket_counts.items()
                if bucket in actionable_buckets and count > 0
            ),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    representative_modules: dict[str, list[str]] = {}
    for bucket, samples in dict(summary.get("action_bucket_samples") or {}).items():
        modules: list[str] = []
        for sample in samples:
            module = str((sample or {}).get("module") or "").strip()
            if module and module not in modules:
                modules.append(module)
        if modules:
            representative_modules[str(bucket)] = modules
    return {
        "immediate_repair_rows": summary.get("immediate_repair_rows"),
        "action_bucket_counts": action_bucket_counts,
        "top_action_buckets": top_action_buckets,
        "representative_modules": representative_modules,
    }


def _handoff_guidance(repo: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    status = build_handoff_status(repo, live=False)
    compact_status = compact_handoff_status(status)
    decision = decide_handoff_action(status)
    if decision.get("command"):
        return compact_status, decision
    return compact_status, None


def _local_repair_status(repo: Path) -> dict[str, Any]:
    plan = _read_optional_json(repo, LOCAL_REPAIR_PLAN_PATH)
    if not isinstance(plan, dict):
        return {
            "present": False,
            "path": LOCAL_REPAIR_PLAN_PATH,
        }
    preflight_report = dict(plan.get("preflight_report") or {})
    runtime_dependencies = dict(preflight_report.get("runtime_dependencies") or {})
    runtime_missing_modules = [
        str(entry.get("module"))
        for entry in list(runtime_dependencies.get("missing") or [])
        if str(entry.get("module") or "").strip()
    ]
    bootstrap_recommendation = _compact_bootstrap_recommendation(
        plan.get("bootstrap_recommendation")
    )
    observed_timeout_s = _observed_runtime_timeout_s(plan, runtime_dependencies)
    timeout_reprobe_recommended = (
        runtime_dependencies.get("ok") is False
        and observed_timeout_s is not None
        and observed_timeout_s < float(LOCAL_REPAIR_RUNTIME_IMPORT_TIMEOUT_S)
        and dict(bootstrap_recommendation or {}).get("reason") == "selected_python_runtime_import_timeouts"
    )
    return {
        "present": True,
        "path": LOCAL_REPAIR_PLAN_PATH,
        "generated_at": plan.get("generated_at"),
        "preflight_ok": preflight_report.get("ok"),
        "local_runtime_ready": runtime_dependencies.get("ok"),
        "observed_timeout_s": observed_timeout_s,
        "timeout_reprobe_recommended": timeout_reprobe_recommended,
        "runtime_missing_modules": runtime_missing_modules,
        "bootstrap_recommendation": bootstrap_recommendation,
    }


def build_report(repo: Path = REPO, requested_intent: str = "auto") -> dict[str, Any]:
    requested_intent = requested_intent.strip().lower()
    if requested_intent not in VALID_INTENTS:
        raise ValueError(f"requested_intent must be one of {VALID_INTENTS}, got {requested_intent!r}")

    decision = _read_json(repo, REMOTE_DECISION_PATH)
    matrix = _read_json(repo, EXPERIMENT_MATRIX_PATH)
    readiness = _read_json(repo, HF_READINESS_PATH)
    readiness_fc128best = _read_json(repo, HF_READINESS_FC128BEST_PATH)
    repair_summary = _read_optional_json(repo, REPAIR_SUMMARY_PATH)
    benchmark_repair_summary = _read_optional_json(repo, BENCHMARK_REPAIR_SUMMARY_PATH)
    failure_analysis = _read_optional_json(repo, FAILURE_ANALYSIS_PATH)
    full_dataset_repair_queue_summary = _read_optional_json(repo, FULL_DATASET_REPAIR_QUEUE_SUMMARY_PATH)
    full_dataset_repair_evidence_summary = _read_optional_json(repo, FULL_DATASET_REPAIR_EVIDENCE_SUMMARY_PATH)
    patch_worklist = _read_optional_json(repo, PATCH_WORKLIST_PATH)
    patch_packets = _read_optional_json(repo, PATCH_PACKETS_PATH)
    full_dataset_validated_repair_pairs_summary = _read_optional_json(
        repo, FULL_DATASET_VALIDATED_REPAIR_PAIRS_SUMMARY_PATH
    )
    full_dataset_harness_repair_pairs_summary = _read_optional_json(
        repo, FULL_DATASET_HARNESS_REPAIR_PAIRS_SUMMARY_PATH
    )
    published_proof_summary = _read_optional_json(repo, PUBLISHED_PROOF_SUMMARY_PATH)
    handoff_status, handoff_prerequisite = _handoff_guidance(repo)
    local_repair_status = _local_repair_status(repo)
    repair_corpus_profile = _recommended_repair_corpus_profile(patch_packets, patch_worklist)
    repair_health = dict((repair_summary or {}).get("health") or {})
    repair_corpus_summary = {
        "rows": (repair_summary or {}).get("rows"),
        "kept_rows_by_source": (repair_summary or {}).get("kept_rows_by_source", {}),
        "missing_sources": (repair_summary or {}).get("missing_sources", []),
    }
    proof_artifact_status = _published_proof_status(published_proof_summary)
    public_benchmark_correctness_status = _public_benchmark_correctness_status(readiness, readiness_fc128best)
    repair_workflow = {
        "recommended_profile": repair_corpus_profile,
        "refresh_command": _repair_refresh_command(repair_corpus_profile),
        "preflight_command": _repair_local_preflight_command(repair_corpus_profile),
        "train_command": _repair_local_train_command(repair_corpus_profile),
        "full_dataset_repair_queue_command": _full_dataset_repair_queue_command(),
        "full_dataset_repair_queue_summary": full_dataset_repair_queue_summary,
        "full_dataset_repair_evidence_command": _full_dataset_repair_evidence_command(),
        "full_dataset_repair_evidence_summary": full_dataset_repair_evidence_summary,
        "patch_worklist_command": _patch_worklist_command(),
        "patch_worklist": patch_worklist,
        "patch_packets_command": _patch_packets_command(),
        "patch_packets_summary": _patch_packets_summary(patch_packets),
        "full_dataset_validated_repair_pairs_command": _full_dataset_validated_repair_pairs_command(),
        "full_dataset_validated_repair_pairs_summary": full_dataset_validated_repair_pairs_summary,
        "full_dataset_harness_repair_pairs_command": _full_dataset_harness_repair_pairs_command(),
        "full_dataset_harness_repair_pairs_summary": full_dataset_harness_repair_pairs_summary,
        "benchmark_gold_coverage": _benchmark_gold_coverage(benchmark_repair_summary),
        "failure_priority": _failure_priority(failure_analysis),
        "repair_corpus_health": repair_health,
        "repair_corpus_summary": repair_corpus_summary,
    }

    recommended_action: str
    recommended_command: str
    preferred_sft_lane: str | None = None
    preferred_publish_model: str | None = None
    recommended_local_command: str | None = None
    rationale: str

    if _decision_blocks_sft(decision):
        recommended_action = "repair"
        recommended_command = _repair_command(repair_corpus_profile)
        recommended_local_command = _repair_local_preflight_command(repair_corpus_profile)
        rationale = "Remote decision still blocks SFT, so the next move is to rebuild repair data and continue repair training."
    else:
        preferred_publish_model, publish_command = _publish_choice(readiness, readiness_fc128best)
        if preferred_publish_model and publish_command:
            recommended_action = "publish"
            recommended_command = publish_command
            rationale = "A publish-readiness report is clear, so the next move is a guarded publish dry-run for the ready benchmark model."
        else:
            preferred_sft_lane = _preferred_sft_lane(matrix)
            if preferred_sft_lane is None:
                recommended_action = "repair"
                recommended_command = _repair_command(repair_corpus_profile)
                rationale = "No trainable comparison lane is available, so the next move falls back to repair work."
            else:
                recommended_action = "sft-preflight"
                recommended_command = _sft_command(preferred_sft_lane)
                recommended_local_command = _local_sft_command(preferred_sft_lane)
                rationale = "Remote gates are open but no publish candidate is ready, so the next move is a bounded SFT preflight on the preferred trainable lane."

    if handoff_prerequisite is not None:
        rationale = (
            f"{rationale} Operational prerequisite: {handoff_prerequisite['reason']} "
            f"({handoff_prerequisite['command']})."
        )
    if recommended_action == "repair" and local_repair_status.get("present") and not local_repair_status.get("preflight_ok"):
        if local_repair_status.get("timeout_reprobe_recommended"):
            rationale = (
                f"{rationale} The current local repair manifest was collected with a shorter "
                f"import timeout than the default bounded probe; rerun local repair preflight "
                f"first ({LOCAL_REPAIR_STATUS_COMMAND})."
            )
        else:
            bootstrap = dict(local_repair_status.get("bootstrap_recommendation") or {})
            if bootstrap.get("command"):
                rationale = (
                    f"{rationale} Local repair preflight is currently not ready on this machine; "
                    f"rerun the local bootstrap path first ({bootstrap['command']})."
                )
            else:
                missing_modules = list(local_repair_status.get("runtime_missing_modules") or [])
                if missing_modules:
                    rationale = (
                        f"{rationale} Local repair preflight is currently not ready on this machine; "
                        f"missing runtime imports: {', '.join(missing_modules)}."
                    )

    intent_allowed = requested_intent in {"auto", recommended_action}
    return {
        "schema": "chattla_tla_prover_next_experiment_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": ".",
        "requested_intent": requested_intent,
        "intent_allowed": intent_allowed,
        "recommended_action": recommended_action,
        "recommended_command": recommended_command,
        "recommended_local_command": recommended_local_command,
        "handoff_status": handoff_status,
        "handoff_prerequisite": handoff_prerequisite,
        "local_repair_status": local_repair_status,
        "local_repair_status_command": LOCAL_REPAIR_STATUS_COMMAND,
        "rationale": rationale,
        "preferred_sft_lane": preferred_sft_lane,
        "preferred_publish_model": preferred_publish_model,
        "preferred_sft_lane_summary": (dict(matrix.get("lanes") or {}).get(preferred_sft_lane) if preferred_sft_lane else None),
        "remote_decision": {
            "verdict": decision.get("verdict"),
            "known18_passed": decision.get("known18_passed"),
            "full_dataset_verdict": decision.get("full_dataset_verdict"),
            "next_action": decision.get("next_action"),
            "full_dataset_next_action": decision.get("full_dataset_next_action"),
        },
        "publish_readiness": {
            "default_model": {
                "benchmark_model": readiness.get("benchmark_model"),
                "ready_to_publish": readiness.get("ready_to_publish"),
                "blockers": readiness.get("blockers", []),
            },
            "fc128best_model": {
                "benchmark_model": readiness_fc128best.get("benchmark_model"),
                "ready_to_publish": readiness_fc128best.get("ready_to_publish"),
                "blockers": readiness_fc128best.get("blockers", []),
            },
        },
        "repair_corpus_health": repair_health,
        "repair_corpus_summary": repair_corpus_summary,
        "repair_workflow": repair_workflow,
        "corpus_expansion_status": _corpus_expansion_status(matrix),
        "repair_expansion_status": _repair_expansion_status(matrix),
        "comparison_plan_commands": _comparison_plan_commands(matrix),
        "proof_artifact_status": proof_artifact_status,
        "public_benchmark_correctness_status": public_benchmark_correctness_status,
    }


def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    handoff_status = dict(report.get("handoff_status") or {})
    handoff_prerequisite = dict(report.get("handoff_prerequisite") or {})
    local_repair_status = dict(report.get("local_repair_status") or {})
    public_benchmark = dict(report.get("public_benchmark_correctness_status") or {})
    repair_corpus_summary = dict(report.get("repair_corpus_summary") or {})
    return {
        "recommended_action": report.get("recommended_action"),
        "recommended_command": report.get("recommended_command"),
        "recommended_local_command": report.get("recommended_local_command"),
        "rationale": report.get("rationale"),
        "preferred_sft_lane": report.get("preferred_sft_lane"),
        "preferred_publish_model": report.get("preferred_publish_model"),
        "handoff_state": handoff_status.get("state"),
        "handoff_next_action": handoff_status.get("next_action"),
        "handoff_prerequisite_action": handoff_prerequisite.get("action"),
        "handoff_prerequisite_command": handoff_prerequisite.get("command"),
        "local_repair_status_present": local_repair_status.get("present"),
        "local_runtime_ready": local_repair_status.get("local_runtime_ready"),
        "local_runtime_missing_modules": local_repair_status.get("runtime_missing_modules"),
        "local_repair_status_command": report.get("local_repair_status_command"),
        "supports_public_benchmark_100_percent_claim": public_benchmark.get(
            "supports_public_benchmark_100_percent_claim"
        ),
        "repair_rows": repair_corpus_summary.get("rows"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--intent", default="auto", choices=VALID_INTENTS)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    parser.add_argument("--compact", action="store_true", help="Print a compact operator-facing JSON summary.")
    args = parser.parse_args()

    report = build_report(args.repo, requested_intent=args.intent)
    payload = compact_report(report) if args.compact else report
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(text)
    return 0 if report["intent_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
