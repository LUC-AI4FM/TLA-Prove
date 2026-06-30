#!/usr/bin/env python3
"""Choose the next local TLA prover action from tracked decision artifacts."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
REMOTE_DECISION_PATH = "outputs/manifests/tla_prover_remote_decision.json"
EXPERIMENT_MATRIX_PATH = "outputs/manifests/tla_prover_corpus_experiment_matrix.json"
HF_READINESS_PATH = "outputs/manifests/hf_publish_readiness.json"
HF_READINESS_FC128BEST_PATH = "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json"
REPAIR_SUMMARY_PATH = "data/processed/tla_prover_repair_train_v1.summary.json"
PUBLISHED_PROOF_SUMMARY_PATH = "outputs/autoprover/tlaps_verify_published_161016/summary.json"
VALID_INTENTS = ("auto", "repair", "sft-preflight", "publish")


def _read_json(repo: Path, rel_path: str) -> dict[str, Any]:
    return json.loads((repo / rel_path).read_text(encoding="utf-8"))


def _read_optional_json(repo: Path, rel_path: str) -> dict[str, Any] | None:
    path = repo / rel_path
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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


def _repair_command() -> str:
    return (
        "python3 scripts/build_benchmark_repair_pairs.py --benchmark-model chattla:20b-fc128best "
        "&& python3 scripts/build_tla_prover_repair_corpus.py "
        "&& python3 -m scripts.train_rl_repair --preflight-only "
        "&& python3 -m scripts.train_rl_repair"
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


def build_report(repo: Path = REPO, requested_intent: str = "auto") -> dict[str, Any]:
    requested_intent = requested_intent.strip().lower()
    if requested_intent not in VALID_INTENTS:
        raise ValueError(f"requested_intent must be one of {VALID_INTENTS}, got {requested_intent!r}")

    decision = _read_json(repo, REMOTE_DECISION_PATH)
    matrix = _read_json(repo, EXPERIMENT_MATRIX_PATH)
    readiness = _read_json(repo, HF_READINESS_PATH)
    readiness_fc128best = _read_json(repo, HF_READINESS_FC128BEST_PATH)
    repair_summary = _read_optional_json(repo, REPAIR_SUMMARY_PATH)
    published_proof_summary = _read_optional_json(repo, PUBLISHED_PROOF_SUMMARY_PATH)
    repair_health = dict((repair_summary or {}).get("health") or {})
    repair_corpus_summary = {
        "rows": (repair_summary or {}).get("rows"),
        "kept_rows_by_source": (repair_summary or {}).get("kept_rows_by_source", {}),
        "missing_sources": (repair_summary or {}).get("missing_sources", []),
    }
    proof_artifact_status = _published_proof_status(published_proof_summary)
    public_benchmark_correctness_status = _public_benchmark_correctness_status(readiness, readiness_fc128best)

    recommended_action: str
    recommended_command: str
    preferred_sft_lane: str | None = None
    preferred_publish_model: str | None = None
    recommended_local_command: str | None = None
    rationale: str

    if _decision_blocks_sft(decision):
        recommended_action = "repair"
        recommended_command = _repair_command()
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
                recommended_command = _repair_command()
                rationale = "No trainable comparison lane is available, so the next move falls back to repair work."
            else:
                recommended_action = "sft-preflight"
                recommended_command = _sft_command(preferred_sft_lane)
                recommended_local_command = _local_sft_command(preferred_sft_lane)
                rationale = "Remote gates are open but no publish candidate is ready, so the next move is a bounded SFT preflight on the preferred trainable lane."

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
        "proof_artifact_status": proof_artifact_status,
        "public_benchmark_correctness_status": public_benchmark_correctness_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--intent", default="auto", choices=VALID_INTENTS)
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    args = parser.parse_args()

    report = build_report(args.repo, requested_intent=args.intent)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    return 0 if report["intent_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
