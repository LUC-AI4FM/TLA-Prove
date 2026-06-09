#!/usr/bin/env python3
"""Collect long verifier-repair trajectories for ChatTLA.

This is the training-data version of the tla-generator/Ralph idea:

    student draft -> SANY/TLC/diamond gate -> teacher or student repair
    -> repeat until final verifier success or repeated malformed output.

The run still records fixed pass@K cutoffs, so models remain comparable even
when the production loop behaves like "until converged".
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.inference.ollama_client import (  # noqa: E402
    ChatTLAClient,
    _build_harmony_prompt,
    _extract_tla,
    _sanitize_spec,
)
from src.rlvr_canary.fullspec_dataset import (  # noqa: E402
    _DEVELOPER_PROMPT,
    load_fullspec_prompts,
)
from src.rlvr_canary.long_ralph_policy import (  # noqa: E402
    LongRunStep,
    failure_signature,
    pass_curve,
    should_stop,
    stable_spec_hash,
)
from src.validators.tlc_validator import validate_string as tlc_validate  # noqa: E402


BRANCH_FOCUSES = {
    "assumptions": (
        "PARALLEL BRANCH FOCUS: remove false assumptions. Replace CONSTANTS plus ASSUME with small "
        "concrete operators like Proc == 1..3, MaxWaiters == 2, or Capacity == 2 so TLC checks the "
        "actual model instead of failing generated assumptions."
    ),
    "ownership": (
        "PARALLEL BRANCH FOCUS: fix ownership and release semantics. V/release actions must require "
        "the releasing process to be the current holder, and wakeup must be part of release behavior."
    ),
    "liveness": (
        "PARALLEL BRANCH FOCUS: fix fairness and liveness. Put weak fairness directly in Spec and "
        "make any liveness/progress property something TLC can check through PROPERTY."
    ),
    "queue": (
        "PARALLEL BRANCH FOCUS: fix waiter and queue modeling. Preserve blocking semantics, bounded "
        "waiters, and FIFO/turn behavior when the requirement implies it."
    ),
    "cfg": (
        "PARALLEL BRANCH FOCUS: fix TLC checkability. Prefer small concrete finite domains, avoid "
        "CONSTANTS plus ASSUME, define Init/Next/Spec/TypeOK plainly, and keep properties named."
    ),
    "simplify": (
        "PARALLEL BRANCH FOCUS: simplify the model. Rewrite the smallest complete TLC-checkable spec "
        "that preserves the requirement, using guarded disjunctive actions instead of fragile helpers."
    ),
}


SYSTEM = r"""You are an expert in TLA+ and the TLC model checker.
Produce a complete pure-TLA+ module that starts with ---- MODULE <Name> ---- and ends with ====.
Start with EXTENDS Naturals, Sequences, FiniteSets, TLC unless there is a clear reason not to.
Define VARIABLES, Init, Next, vars, Spec, TypeOK, and at least one meaningful safety invariant.
Prefer concrete finite model definitions over CONSTANTS and ASSUME, e.g. Proc == 1..3 and MaxWaiters == 2.
Do not add ASSUME lines for bounds or non-emptiness unless the requirement truly needs constants.
If the requirement mentions waiting, blocking, progress, fairness, or eventual behavior, define an explicit
liveness/progress property and add appropriate weak fairness to Spec.
For actions with cases, prefer guarded disjunctions (\\\/ /\\ guard /\\ updates) instead of IF/THEN/ELSE.
If you use IF, it must always include both THEN and ELSE.
Every action branch must assign each variable exactly once, either with x' = ... or UNCHANGED x.
Put fairness in Spec itself; TLC checks Spec, not an unused SpecWithFairness operator.
Cardinality requires EXTENDS FiniteSets; if unsure, avoid Cardinality and use quantified invariants.
Keep all constants finite and small so TLC terminates. Output only the module, no markdown."""


DIFF_SYSTEM = r"""You are an expert in TLA+ and the TLC model checker.
Repair the existing TLA+ module by returning a unified diff patch against the previous spec.
Make the smallest semantic change that fixes the verifier feedback without weakening the requirement.
Keep the module name unchanged. Do not rename operators unless the feedback requires it.
Prefer targeted edits over rewriting the whole file.
Return only a unified diff with hunk headers, no prose and no markdown.
Use standard diff lines starting with --- , +++ , @@ , space, -, or +."""


FREEZE_SYSTEM = """You extract TLA+ properties from natural-language requirements.
Output only TLA+ operator definitions of key state safety predicates, one to three definitions.
Do not use temporal operators like [], <>, WF_, SF_, ENABLED, or primed variables.
These definitions may be used as invariants, so keep them state-level and finite-model friendly.
Only use variable names that are explicit in the requirement. If the requirement does not name
concrete variables, output nothing.
No MODULE header, no prose, no markdown."""


JUDGE_SYSTEM = """You are the final adequacy judge for generated TLA+ specifications.
The spec has already passed SANY and TLC, so do not re-check syntax.
Decide whether the specification actually models the user's natural-language requirement.

Check for omitted actors, weakened safety properties, wrong state transitions, missing liveness
when requested, vacuous invariants, and tiny models that pass while ignoring the intended system.

Output exactly one of:
OK
NOT_OK: <one concise reason the spec must be repaired>
"""


class Generator(Protocol):
    name: str

    def initial(self, description: str, module: str, frozen: str) -> str:
        ...

    def repair(
        self,
        description: str,
        module: str,
        previous_spec: str,
        diagnostics: str,
        iteration: int,
        frozen: str,
        repair_mode: str,
    ) -> str:
        ...


class LocalChatTLA:
    def __init__(self, model: str, temperature: float) -> None:
        self.name = f"local:{model}"
        self.model = model
        self.temperature = temperature
        self.client = ChatTLAClient(model=model, reasoning="high")

    def initial(self, description: str, module: str, frozen: str) -> str:
        prompt = _with_frozen(description, frozen)
        return self.client.generate_spec(
            prompt, module_name=module, temperature=self.temperature, rag_k=2
        )

    def repair(
        self,
        description: str,
        module: str,
        previous_spec: str,
        diagnostics: str,
        iteration: int,
        frozen: str,
        repair_mode: str,
    ) -> str:
        if repair_mode == "diff":
            return self._repair_diff(description, module, previous_spec, diagnostics, iteration, frozen)
        return self._repair_full(description, module, previous_spec, diagnostics, iteration, frozen)

    def _repair_full(
        self,
        description: str,
        module: str,
        previous_spec: str,
        diagnostics: str,
        iteration: int,
        frozen: str,
    ) -> str:
        user = _repair_user(description, module, previous_spec, diagnostics, iteration, frozen)
        prompt = _build_harmony_prompt(
            f"{_DEVELOPER_PROMPT}\nReasoning: high",
            user,
        )
        response = self.client._client.generate(
            model=self.model,
            prompt=prompt,
            raw=True,
            options={
                "temperature": min(0.95, self.temperature + 0.05 * iteration),
                "repeat_penalty": 1.3,
                "num_predict": 4096,
                "top_k": 40,
                "top_p": 0.9,
                "stop": ["<|return|>", "<|end|>", "<|start|>"],
            },
        )
        return _sanitize_spec(_extract_tla("---- MODULE" + response["response"]))

    def _repair_diff(
        self,
        description: str,
        module: str,
        previous_spec: str,
        diagnostics: str,
        iteration: int,
        frozen: str,
    ) -> str:
        user = _repair_diff_user(description, module, previous_spec, diagnostics, iteration, frozen)
        prompt = _build_harmony_prompt(
            f"{DIFF_SYSTEM}\nReasoning: high",
            user,
        )
        response = self.client._client.generate(
            model=self.model,
            prompt=prompt,
            raw=True,
            options={
                "temperature": min(0.7, self.temperature + 0.03 * iteration),
                "repeat_penalty": 1.2,
                "num_predict": 2048,
                "top_k": 40,
                "top_p": 0.9,
                "stop": ["<|return|>", "<|end|>", "<|start|>"],
            },
        )
        patched = _patched_spec_from_response(previous_spec, response.get("response", ""))
        if patched:
            return patched
        return self._repair_full(description, module, previous_spec, diagnostics, iteration, frozen)


class OllamaCloud:
    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        url: str = "https://ollama.com/api/chat",
        temperature: float = 0.25,
        timeout: int = 240,
    ) -> None:
        self.name = f"ollama-cloud:{model}"
        self.model = model
        self.api_key = api_key
        self.url = url
        self.temperature = temperature
        self.timeout = timeout

    def _chat(self, messages: list[dict[str, str]], temperature: float | None = None) -> str:
        import requests

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature if temperature is None else temperature},
        }
        response = requests.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            raise RuntimeError(data["error"])
        message = data.get("message") or {}
        return message.get("content") or data.get("response") or ""

    def review(self, messages: list[dict[str, str]]) -> str:
        return self._chat(messages, temperature=0.1)

    def initial(self, description: str, module: str, frozen: str) -> str:
        user = (
            f"Write a complete TLC-checkable TLA+ module named {module}.\n\n"
            f"System description:\n{_with_frozen(description, frozen)}"
        )
        return _sanitize_spec(_extract_tla(self._chat([
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ])))

    def repair(
        self,
        description: str,
        module: str,
        previous_spec: str,
        diagnostics: str,
        iteration: int,
        frozen: str,
        repair_mode: str,
    ) -> str:
        if repair_mode == "diff":
            raw = self._chat([
                {"role": "system", "content": DIFF_SYSTEM},
                {
                    "role": "user",
                    "content": _repair_diff_user(
                        description, module, previous_spec, diagnostics, iteration, frozen
                    ),
                },
            ], temperature=min(0.55, self.temperature + 0.02 * iteration))
            patched = _patched_spec_from_response(previous_spec, raw)
            if patched:
                return patched
        return _sanitize_spec(_extract_tla(self._chat([
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": _repair_user(
                    description, module, previous_spec, diagnostics, iteration, frozen
                ),
            },
        ], temperature=min(0.7, self.temperature + 0.03 * iteration))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--student-model", default=os.getenv("CHATTLA_STUDENT_MODEL", "chattla:20b"))
    parser.add_argument("--teacher-model", default=os.getenv("OLLAMA_CLOUD_MODEL", "qwen3-coder:480b"))
    parser.add_argument("--initial-provider", choices=["student", "teacher"], default="student")
    parser.add_argument("--repair-provider", choices=["student", "teacher", "alternate"], default="teacher")
    parser.add_argument("--success-gate", choices=["gold", "diamond"], default=os.getenv("CHATTLA_SUCCESS_GATE", "diamond"))
    parser.add_argument(
        "--max-iters",
        type=int,
        default=0,
        help="Optional per-prompt watchdog. 0 means run until verified success or malformed-output stop.",
    )
    parser.add_argument("--max-prompts", type=int, default=120)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--tlc-timeout", type=int, default=45)
    parser.add_argument("--no-improvement-limit", type=int, default=8)
    parser.add_argument("--repeated-signature-limit", type=int, default=4)
    parser.add_argument("--repeated-spec-limit", type=int, default=3)
    parser.add_argument("--malformed-limit", type=int, default=3)
    parser.add_argument("--max-same-failure-family-iters", type=int, default=24)
    parser.add_argument("--max-frontier-stall-iters", type=int, default=96)
    parser.add_argument("--semantic-stall-stop", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--branch-after-iters", type=int, default=20)
    parser.add_argument("--branch-width", type=int, default=5)
    parser.add_argument("--branch-iters", type=int, default=8)
    parser.add_argument("--out-trajectories", default="data/processed/long_ralph/trajectories.jsonl")
    parser.add_argument("--out-pairs", default="data/processed/long_ralph/repair_pairs.jsonl")
    parser.add_argument("--out-step-events", default="data/processed/long_ralph/step_events.jsonl")
    parser.add_argument("--out-live-pairs", default="data/processed/long_ralph/repair_pairs_live.jsonl")
    parser.add_argument("--out-accepted-dir", default="data/processed/long_ralph/accepted_specs")
    parser.add_argument("--run-report", default="")
    parser.add_argument("--summary", default="data/processed/long_ralph/summary.json")
    parser.add_argument("--freeze-properties", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--final-judge", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--acceptance-mode",
        choices=["proof", "audit"],
        default=os.getenv("CHATTLA_ACCEPTANCE_MODE", "audit"),
        help="proof stops at SANY/TLC/semantic gate; audit also requires modeling-audit gates.",
    )
    parser.add_argument("--local-model-audit", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--repair-mode", choices=["full", "diff"], default="diff")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not (0 <= args.shard_index < args.num_shards):
        parser.error("--shard-index must be in [0, --num-shards)")

    api_key = os.getenv("OLLAMA_API_KEY", "")
    needs_teacher = (
        args.initial_provider == "teacher"
        or args.repair_provider in {"teacher", "alternate"}
        or args.freeze_properties
        or (args.final_judge and args.acceptance_mode == "audit")
    )
    if needs_teacher and not api_key and not args.dry_run:
        raise SystemExit("OLLAMA_API_KEY is required. Source ~/.config/chattla/ollama.env first.")

    examples = load_fullspec_prompts(
        include_topics=True,
        include_diamond_sft=True,
        include_train=False,
        max_per_source=None,
    )
    examples = [
        ex for i, ex in enumerate(examples)
        if i % args.num_shards == args.shard_index
    ][: args.max_prompts]

    print(
        json.dumps({
            "student_model": args.student_model,
            "teacher_model": args.teacher_model,
            "initial_provider": args.initial_provider,
            "repair_provider": args.repair_provider,
            "repair_mode": args.repair_mode,
            "success_gate": args.success_gate,
            "acceptance_mode": args.acceptance_mode,
            "local_model_audit": args.local_model_audit,
            "final_judge": args.final_judge,
            "freeze_properties": args.freeze_properties,
            "semantic_stall_stop": args.semantic_stall_stop,
            "max_same_failure_family_iters": args.max_same_failure_family_iters,
            "max_frontier_stall_iters": args.max_frontier_stall_iters,
            "branch_after_iters": args.branch_after_iters,
            "branch_width": args.branch_width,
            "branch_iters": args.branch_iters,
            "max_iters": args.max_iters,
            "max_prompts": len(examples),
            "shard": f"{args.shard_index}/{args.num_shards}",
        }, indent=2)
    )
    if args.dry_run:
        return 0

    student = LocalChatTLA(args.student_model, temperature=0.25)
    teacher = OllamaCloud(args.teacher_model, api_key, temperature=0.25)

    traj_path = _abs(args.out_trajectories)
    pair_path = _abs(args.out_pairs)
    step_path = _abs(args.out_step_events)
    live_pair_path = _abs(args.out_live_pairs)
    accepted_dir = _abs(args.out_accepted_dir)
    summary_path = _abs(args.summary)
    traj_path.parent.mkdir(parents=True, exist_ok=True)
    pair_path.parent.mkdir(parents=True, exist_ok=True)
    step_path.parent.mkdir(parents=True, exist_ok=True)
    live_pair_path.parent.mkdir(parents=True, exist_ok=True)
    accepted_dir.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    step_path.write_text("", encoding="utf-8")
    live_pair_path.write_text("", encoding="utf-8")

    summaries: list[dict] = []
    with traj_path.open("w", encoding="utf-8") as tf, pair_path.open("w", encoding="utf-8") as pf:
        for ex in examples:
            traj = run_one(ex, student, teacher, args)
            tf.write(json.dumps(traj) + "\n")
            tf.flush()
            accepted_path = save_accepted_spec(traj, accepted_dir)
            if accepted_path:
                print(f"[long-ralph] accepted spec -> {accepted_path}")
            for pair in flatten_pairs(traj):
                pf.write(json.dumps(pair) + "\n")
            pf.flush()
            summaries.append(summarize_trajectory(traj) | {
                "prompt_id": traj["prompt_id"],
                "success": traj["success"],
                "iterations": traj["iterations"],
                "stop_reason": traj["stop_reason"],
                "best_score": traj["best_score"],
                "best_tier": traj["best_tier"],
            })
            if args.run_report:
                write_run_report(_abs(args.run_report), summaries)

    summary = {
        "created_at": int(time.time()),
        "num_trajectories": len(summaries),
        "num_success": sum(1 for row in summaries if row["success"]),
        "pass_curve": pass_curve(summaries),
        "failure_families": aggregate_failure_families(summaries),
        "rows": summaries,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if args.run_report:
        write_run_report(_abs(args.run_report), summaries)
    print(json.dumps(summary["pass_curve"], indent=2))
    print(f"[long-ralph] trajectories -> {traj_path}")
    print(f"[long-ralph] repair pairs -> {pair_path}")
    print(f"[long-ralph] step events -> {step_path}")
    print(f"[long-ralph] live repair pairs -> {live_pair_path}")
    print(f"[long-ralph] accepted specs -> {accepted_dir}")
    print(f"[long-ralph] summary -> {summary_path}")
    return 0


def run_one(ex, student: Generator, teacher: OllamaCloud, args: argparse.Namespace) -> dict:
    print(f"\n[long-ralph] {ex.prompt_id} module={ex.module_name}")
    frozen = ""
    if args.freeze_properties:
        frozen = freeze_properties(teacher, ex.nl_description)
        if frozen:
            print(f"  frozen: {frozen[:100].replace(chr(10), ' ')}")

    policy_steps: list[LongRunStep] = []
    raw_steps: list[dict] = []
    best_score = 0.0
    best_tier = "malformed"
    best_spec = ""
    stop_reason = "max_iters"
    branch_round = 0
    last_branch_at = 0

    n = 0
    while True:
        n += 1
        gen = pick_generator(n, args, student, teacher)
        parent = select_repair_parent(raw_steps)
        step = generate_step(
            ex, gen, teacher, args, frozen,
            previous_spec=parent.get("spec", "") if parent else "",
            diagnostics=repair_context_for_parent(parent, raw_steps),
            iteration=n,
            parent_iteration=parent.get("iteration") if parent else None,
            history=raw_steps,
        )
        best_score, best_tier, best_spec = update_best(
            step, best_score, best_tier, best_spec,
        )
        record_step(ex, frozen, step, args, raw_steps, policy_steps, parent)

        print_step(step)

        if should_stop_for_semantic_stall(raw_steps, args):
            stop_reason = "semantic_stall"
            break
        if should_stop_for_frontier_stall(raw_steps, args):
            stop_reason = "frontier_stall"
            break

        decision = should_stop(
            policy_steps,
            max_iters=args.max_iters,
            repeated_signature_limit=args.repeated_signature_limit,
            repeated_spec_limit=args.repeated_spec_limit,
            no_improvement_limit=args.no_improvement_limit,
            malformed_limit=args.malformed_limit,
        )
        if decision.stop:
            stop_reason = decision.reason
            break

        if should_start_parallel_branches(raw_steps, args, last_branch_at):
            branch_round += 1
            root = select_repair_parent(raw_steps) or raw_steps[-1]
            results = run_parallel_branches(
                ex, teacher, args, frozen, root, branch_round,
            )
            selected = select_branch_result(results)
            for result in branch_results_for_recording(results, selected):
                branch_steps = result.get("steps") or []
                iteration_map = {root.get("iteration"): root.get("iteration")}
                for branch_step in branch_steps:
                    old_iteration = branch_step.get("iteration")
                    old_parent_iteration = branch_step.get("parent_iteration")
                    n += 1
                    branch_step["iteration"] = n
                    branch_step["parent_iteration"] = iteration_map.get(
                        old_parent_iteration,
                        root.get("iteration"),
                    )
                    iteration_map[old_iteration] = n
                    parent_for_record = step_by_iteration(
                        raw_steps,
                        branch_step.get("parent_iteration"),
                    )
                    branch_step["repair_context"] = rebuild_step_context(
                        branch_step, raw_steps + [branch_step],
                    )
                    best_score, best_tier, best_spec = update_best(
                        branch_step, best_score, best_tier, best_spec,
                    )
                    record_step(
                        ex, frozen, branch_step, args,
                        raw_steps, policy_steps, parent_for_record,
                    )
                    print_step(branch_step)
            last_branch_at = n

            selected_step = selected_final_step(selected)
            if selected_step:
                if selected_step["success"]:
                    stop_reason = "success"
                    break

    success = bool(raw_steps and raw_steps[-1]["success"])
    return {
        "prompt_id": ex.prompt_id,
        "nl": ex.nl_description,
        "module_name": ex.module_name,
        "domain": ex.domain,
        "success": success,
        "iterations": len(raw_steps),
        "stop_reason": stop_reason,
        "best_score": best_score,
        "best_tier": best_tier,
        "best_spec": best_spec,
        "last_failure_family": raw_steps[-1].get("failure_family", "") if raw_steps else "",
        "semantic_stall_count": same_failure_family_tail_count(raw_steps),
        "frontier_stall_count": frontier_stall_count(raw_steps),
        "frozen_properties": frozen,
        "steps": raw_steps,
    }


def generate_step(
    ex,
    gen: Generator,
    teacher: OllamaCloud,
    args: argparse.Namespace,
    frozen: str,
    *,
    previous_spec: str,
    diagnostics: str,
    iteration: int,
    parent_iteration: int | None,
    history: list[dict],
    branch_id: str = "main",
    branch_focus: str = "",
    branch_depth: int = 0,
    branch_directive: str = "",
) -> dict:
    t0 = time.monotonic()
    raw = (
        gen.initial(ex.nl_description, ex.module_name, frozen)
        if parent_iteration is None
        else gen.repair(
            ex.nl_description,
            ex.module_name,
            previous_spec,
            diagnostics,
            iteration,
            frozen,
            args.repair_mode,
        )
    )
    spec = _sanitize_spec(_extract_tla(raw))
    verdict = validate_candidate(spec, args.success_gate, args.tlc_timeout)
    proof_success = bool(verdict["success"])
    verdict["proof_success"] = proof_success
    verdict["model_audit_ok"] = None
    verdict["model_audit_reason"] = ""
    if proof_success and args.acceptance_mode == "audit" and args.local_model_audit:
        audit_ok, audit_reason = audit_candidate(
            ex.nl_description, frozen, spec, verdict["semantic"]
        )
        verdict["model_audit_ok"] = audit_ok
        verdict["model_audit_reason"] = audit_reason
        if not audit_ok:
            verdict["success"] = False
            verdict["phase"] = "adequacy"
            verdict["diagnostics"] = audit_reason

    if verdict["success"] and args.acceptance_mode == "audit" and args.final_judge:
        judge_ok, judge_reason = judge_candidate(
            teacher, ex.nl_description, frozen, spec, verdict["semantic"]
        )
        verdict["judge_ok"] = judge_ok
        verdict["judge_reason"] = judge_reason
        if not judge_ok:
            verdict["success"] = False
            verdict["phase"] = "adequacy"
            verdict["diagnostics"] = judge_reason
    elif verdict["success"]:
        verdict["judge_ok"] = None
        verdict["judge_reason"] = ""

    sig = failure_signature(verdict["phase"], verdict["diagnostics"])
    failure_family = classify_failure_family(verdict)
    step = {
        "iteration": iteration,
        "parent_iteration": parent_iteration,
        "branch_id": branch_id,
        "branch_focus": branch_focus,
        "branch_depth": branch_depth,
        "generator": gen.name,
        "elapsed": round(time.monotonic() - t0, 2),
        "module": verdict["module"],
        "tier": verdict["tier"],
        "raw_score": verdict["score"],
        "score": 0.0,
        "proof_success": verdict.get("proof_success", False),
        "success": verdict["success"],
        "diamond": verdict["diamond"],
        "model_audit_ok": verdict.get("model_audit_ok"),
        "model_audit_reason": verdict.get("model_audit_reason", ""),
        "judge_ok": verdict.get("judge_ok"),
        "judge_reason": verdict.get("judge_reason", ""),
        "phase": verdict["phase"],
        "failure_signature": sig,
        "failure_family": failure_family,
        "spec_hash": stable_spec_hash(spec),
        "malformed": verdict["malformed"],
        "diagnostics": verdict["diagnostics"],
        "semantic": verdict["semantic"],
        "spec": spec,
    }
    step["score"] = objective_score(step)
    step["repair_context"] = rebuild_step_context(
        step, history + [step], branch_directive=branch_directive,
    )
    return step


def rebuild_step_context(step: dict, history: list[dict], branch_directive: str = "") -> str:
    context = build_repair_context(step, history)
    if branch_directive:
        context = _trim_context(f"{context}\n\n{branch_directive}", limit=5000)
    return context


def record_step(
    ex,
    frozen: str,
    step: dict,
    args: argparse.Namespace,
    raw_steps: list[dict],
    policy_steps: list[LongRunStep],
    parent: dict | None,
) -> None:
    if parent:
        append_live_pair(ex, frozen, parent, step, args)
    raw_steps.append(step)
    append_step_event(ex, frozen, step, args)
    policy_steps.append(LongRunStep(
        iteration=step["iteration"],
        score=step["score"],
        phase=step["phase"],
        failure_signature=step["failure_signature"],
        spec_hash=step["spec_hash"],
        success=step["success"],
        malformed=step["malformed"],
    ))


def print_step(step: dict) -> None:
    judge_status = _judge_status(step)
    branch = ""
    if step.get("branch_id") and step.get("branch_id") != "main":
        branch = f" branch={step['branch_id']}:{step.get('branch_focus', '')}/{step.get('branch_depth', 0)}"
    print(
        f"  iter {step['iteration']:02d}: {step['generator']} tier={step['tier']} "
        f"score={step['score']:.3f} success={step['success']} "
        f"phase={step['phase']} family={step['failure_family']}{branch}{judge_status} "
        f"({step['elapsed']}s)"
    )
    if step["phase"] == "adequacy" and step.get("judge_reason"):
        print(f"    judge_reason: {_compact(step['judge_reason'], 260)}")
    elif not step["success"] and step.get("diagnostics"):
        print(f"    diagnostic: {_compact(step['diagnostics'], 260)}")


def update_best(step: dict, best_score: float, best_tier: str, best_spec: str) -> tuple[float, str, str]:
    if step["score"] > best_score:
        return step["score"], step["tier"], step["spec"]
    return best_score, best_tier, best_spec


def objective_score(step: dict) -> float:
    if step.get("success") and step.get("judge_ok") is not False:
        return 1.0

    raw = max(0.0, min(1.0, float(step.get("raw_score") or 0.0)))
    phase = step.get("phase") or ""
    floor, cap = {
        "sany": (0.0, 0.24),
        "tlc": (0.25, 0.54),
        "adequacy": (0.55, 0.84),
        "success": (0.95, 0.99),
    }.get(phase, (0.0, 0.54))
    score = floor + raw * (cap - floor)

    semantic = step.get("semantic") or {}
    family = step.get("failure_family") or ""
    if family == "declared_but_unchecked_liveness":
        score = min(score, 0.60)
    elif family == "false_assumption":
        score = min(score, 0.45)
    elif family == "zero_action_coverage":
        score = min(score, 0.50)
    elif family == "vacuous_safety":
        score = min(score, 0.58)
    elif family.startswith("syntax"):
        score = min(score, 0.20)

    properties_declared = bool(semantic.get("properties_declared"))
    properties_checked = int(semantic.get("properties_checked") or 0)
    if properties_declared and properties_checked == 0:
        score = min(score, 0.60)
    if int(semantic.get("distinct_states") or 0) <= 1:
        score = min(score, 0.58)
    if int(semantic.get("total_actions") or 0) == 0 or float(semantic.get("action_coverage") or 0.0) == 0.0:
        score = min(score, 0.50)
    if step.get("judge_ok") is False:
        score = min(score, 0.84)

    return round(max(0.0, min(score, 1.0)), 4)


def acceptance_frontier_key(step: dict) -> tuple:
    semantic = step.get("semantic") or {}
    phase_order = {"sany": 0, "tlc": 1, "adequacy": 2, "success": 3}
    tier_order = {"malformed": 0, "bronze": 1, "silver": 2, "gold": 3}
    family_order = {
        "success": 9,
        "bad_ownership": 8,
        "weak_fairness": 8,
        "property_violation": 7,
        "declared_but_unchecked_liveness": 6,
        "adequacy": 6,
        "tlc": 5,
        "false_assumption": 4,
        "vacuous_safety": 3,
        "zero_action_coverage": 2,
        "syntax_fairness": 1,
        "syntax_unknown_operator": 1,
        "syntax_precedence": 1,
        "syntax_if_then_else": 1,
        "syntax": 1,
        "malformed": 0,
    }
    properties_declared = bool(semantic.get("properties_declared"))
    properties_checked = int(semantic.get("properties_checked") or 0)
    return (
        int(bool(step.get("success"))),
        int(step.get("judge_ok") is True),
        phase_order.get(step.get("phase", ""), 0),
        int((not properties_declared) or properties_checked > 0),
        int(int(semantic.get("distinct_states") or 0) > 1),
        int(
            int(semantic.get("total_actions") or 0) > 0
            and float(semantic.get("action_coverage") or 0.0) > 0.0
        ),
        family_order.get(step.get("failure_family", ""), 0),
        int(bool(step.get("diamond"))),
        tier_order.get(step.get("tier", ""), 0),
        float(step.get("score") or 0.0),
    )


def frontier_stall_count(steps: list[dict]) -> int:
    if not steps:
        return 0
    best_key = acceptance_frontier_key(steps[0])
    best_index = 0
    for idx, step in enumerate(steps[1:], start=1):
        key = acceptance_frontier_key(step)
        if key > best_key:
            best_key = key
            best_index = idx
    return len(steps) - best_index - 1


def should_start_parallel_branches(
    steps: list[dict],
    args: argparse.Namespace,
    last_branch_at: int,
) -> bool:
    if args.branch_width <= 1 or args.branch_after_iters <= 0 or args.branch_iters <= 0:
        return False
    if not steps or steps[-1].get("success"):
        return False
    if frontier_stall_count(steps) < args.branch_after_iters:
        return False
    return (len(steps) - last_branch_at) >= args.branch_after_iters


def run_parallel_branches(
    ex,
    teacher: OllamaCloud,
    args: argparse.Namespace,
    frozen: str,
    root: dict,
    branch_round: int,
) -> list[dict]:
    focuses = branch_focuses_for_family(root.get("failure_family", ""), args.branch_width)
    print(
        f"  fanout {branch_round}: launching {len(focuses)} branches x "
        f"{args.branch_iters} from iter {root['iteration']} family={root.get('failure_family', '')}"
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(focuses)) as pool:
        futures = {
            pool.submit(
                run_branch,
                ex, teacher, args, frozen, root, branch_round, idx, focus_name, directive,
            ): (idx, focus_name)
            for idx, (focus_name, directive) in enumerate(focuses, start=1)
        }
        results = []
        for future in concurrent.futures.as_completed(futures):
            idx, focus_name = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                branch_id = f"r{branch_round}b{idx}"
                print(f"    branch {branch_id}:{focus_name} failed: {exc}")
                results.append({"branch_id": branch_id, "branch_focus": focus_name, "steps": []})
        return results


def run_branch(
    ex,
    teacher: OllamaCloud,
    args: argparse.Namespace,
    frozen: str,
    root: dict,
    branch_round: int,
    branch_index: int,
    focus_name: str,
    directive: str,
) -> dict:
    branch_id = f"r{branch_round}b{branch_index}"
    branch_directive = (
        f"{directive}\n"
        "This is one parallel branch. Make a decisive semantic repair aligned to this focus; "
        "do not preserve a failing structure just because recent attempts did."
    )
    steps: list[dict] = []
    root_iteration = int(root.get("iteration") or 0)
    for depth in range(1, args.branch_iters + 1):
        branch_history = [root] + steps
        parent = select_repair_parent(branch_history) or root
        step = generate_step(
            ex, teacher, teacher, args, frozen,
            previous_spec=parent.get("spec", ""),
            diagnostics=_trim_context(
                f"{repair_context_for_parent(parent, branch_history)}\n\n{branch_directive}"
            ),
            iteration=root_iteration + depth,
            parent_iteration=parent.get("iteration"),
            history=branch_history,
            branch_id=branch_id,
            branch_focus=focus_name,
            branch_depth=depth,
            branch_directive=branch_directive,
        )
        steps.append(step)
        if step["success"]:
            break
    return {
        "branch_id": branch_id,
        "branch_focus": focus_name,
        "steps": steps,
    }


def branch_focuses_for_family(family: str, width: int) -> list[tuple[str, str]]:
    orders = {
        "false_assumption": ["assumptions", "cfg", "simplify", "queue", "liveness"],
        "bad_ownership": ["ownership", "queue", "simplify", "liveness", "cfg"],
        "weak_fairness": ["liveness", "queue", "ownership", "cfg", "simplify"],
        "declared_but_unchecked_liveness": ["cfg", "liveness", "simplify", "queue", "ownership"],
        "property_violation": ["liveness", "cfg", "queue", "simplify", "ownership"],
        "syntax_precedence": ["simplify", "cfg", "ownership", "queue", "liveness"],
        "syntax_if_then_else": ["simplify", "ownership", "queue", "cfg", "liveness"],
        "syntax_unknown_operator": ["cfg", "simplify", "queue", "ownership", "liveness"],
        "vacuous_safety": ["simplify", "ownership", "liveness", "queue", "cfg"],
        "zero_action_coverage": ["simplify", "ownership", "queue", "liveness", "cfg"],
    }
    order = orders.get(family, ["ownership", "liveness", "queue", "cfg", "assumptions"])
    out: list[tuple[str, str]] = []
    while len(out) < max(0, width):
        name = order[len(out) % len(order)]
        out.append((name, BRANCH_FOCUSES[name]))
    return out


def select_branch_result(results: list[dict]) -> dict:
    if not results:
        return {}
    return max(results, key=branch_result_key)


def branch_result_key(result: dict) -> tuple:
    step = selected_final_step(result)
    if not step:
        return (0, 0, 0.0, 0, 0, 0, 0)
    return acceptance_frontier_key(step) + (-int(step.get("iteration") or 0),)


def selected_final_step(result: dict | None) -> dict | None:
    if not result:
        return None
    steps = result.get("steps") or []
    return max(steps, key=acceptance_frontier_key) if steps else None


def select_repair_parent(steps: list[dict]) -> dict | None:
    if not steps:
        return None
    return max(steps, key=acceptance_frontier_key)


def step_by_iteration(steps: list[dict], iteration: int | None) -> dict | None:
    for step in reversed(steps):
        if step.get("iteration") == iteration:
            return step
    return None


def repair_context_for_parent(parent: dict | None, history: list[dict]) -> str:
    if not parent:
        return ""
    context = parent.get("repair_context") or parent.get("diagnostics", "")
    latest = history[-1] if history else parent
    if latest is parent or latest.get("iteration") == parent.get("iteration"):
        return context

    latest_reason = latest.get("judge_reason") or latest.get("diagnostics") or ""
    note = (
        "Repair from the strongest current frontier candidate below. "
        "A newer attempt regressed and is provided only as a warning, not as the base spec.\n"
        f"Regressed attempt: iter={latest.get('iteration')} tier={latest.get('tier')} "
        f"phase={latest.get('phase')} family={latest.get('failure_family')} "
        f"reason={_compact(latest_reason, 220)}"
    )
    return _trim_context(f"{context}\n\n{note}")


def branch_results_for_recording(results: list[dict], selected: dict) -> list[dict]:
    selected_id = selected.get("branch_id") if selected else ""
    others = sorted(
        [result for result in results if result.get("branch_id") != selected_id],
        key=lambda result: result.get("branch_id", ""),
    )
    return others + ([selected] if selected else [])


def pick_generator(n: int, args: argparse.Namespace, student: Generator, teacher: OllamaCloud) -> Generator:
    if n == 1:
        return teacher if args.initial_provider == "teacher" else student
    if args.repair_provider == "teacher":
        return teacher
    if args.repair_provider == "student":
        return student
    return teacher if n % 2 == 0 else student


def validate_candidate(spec: str, success_gate: str, tlc_timeout: int) -> dict:
    module = _module_name(spec)
    malformed = not module or "====" not in spec
    if malformed:
        return {
            "module": module or "Generated",
            "tier": "malformed",
            "score": 0.0,
            "success": False,
            "diamond": False,
            "phase": "sany",
            "diagnostics": "No extractable `---- MODULE Name ---- ... ====` block.",
            "malformed": True,
            "semantic": {},
            "judge_ok": None,
            "judge_reason": "",
        }

    result = tlc_validate(spec, module_name=module, timeout=tlc_timeout)
    diamond = result.is_diamond
    success = result.tier == "gold" if success_gate == "gold" else diamond
    score = float(result.semantic.partial_credit or 0.0)
    if result.tier == "gold" and not diamond:
        score = max(score, 0.85)

    if result.tier == "bronze":
        phase = "sany"
        diagnostics = _validator_diagnostics(result.sany_errors, result.raw_output)
    elif result.tier == "silver":
        phase = "tlc"
        diagnostics = _validator_diagnostics(result.tlc_violations, result.raw_output)
    elif not diamond and success_gate == "diamond":
        phase = "adequacy"
        diagnostics = _semantic_gap(result.semantic)
    else:
        phase = "success"
        diagnostics = "SANY and TLC passed."

    return {
        "module": module,
        "tier": result.tier,
        "score": score,
        "success": success,
        "diamond": diamond,
        "phase": phase,
        "diagnostics": diagnostics[-3000:],
        "malformed": False,
        "semantic": asdict(result.semantic),
        "judge_ok": None,
        "judge_reason": "",
    }


def flatten_pairs(traj: dict) -> list[dict]:
    pairs: list[dict] = []
    steps = traj.get("steps", [])
    by_iteration = {
        step.get("iteration"): step
        for step in steps
        if step.get("iteration") is not None
    }
    for step in steps:
        parent_iteration = step.get("parent_iteration")
        if parent_iteration is None:
            continue
        before = by_iteration.get(parent_iteration)
        if before:
            pairs.append(_repair_pair(traj, before, step, len(pairs) + 1))
    return pairs


def append_step_event(ex, frozen: str, step: dict, args: argparse.Namespace) -> None:
    _append_jsonl(args.out_step_events, {
        "prompt_id": ex.prompt_id,
        "nl": ex.nl_description,
        "module_name": ex.module_name,
        "domain": ex.domain,
        "frozen_properties": frozen,
        "step": step,
    })


def append_live_pair(ex, frozen: str, before: dict, after: dict, args: argparse.Namespace) -> None:
    traj = {
        "prompt_id": ex.prompt_id,
        "nl": ex.nl_description,
        "module_name": ex.module_name,
        "domain": ex.domain,
        "frozen_properties": frozen,
    }
    _append_jsonl(args.out_live_pairs, _repair_pair(traj, before, after, before["iteration"]))


def _repair_pair(traj: dict, before: dict, after: dict, pair_index: int) -> dict:
    return {
        "repair_id": f"{traj['prompt_id']}_long_{pair_index}to{pair_index + 1}",
        "nl": traj["nl"],
        "broken_spec": before["spec"],
        "errors_rendered": before.get("repair_context") or before["diagnostics"],
        "verify_summary": (
            f"tier={before['tier']} phase={before['phase']} "
            f"score={before['score']:.3f}"
        ),
        "before_score": before["score"],
        "before_raw_score": before.get("raw_score", before["score"]),
        "repaired_spec": after["spec"],
        "after_score": after["score"],
        "after_raw_score": after.get("raw_score", after["score"]),
        "before_diamond": before["diamond"],
        "after_diamond": after["diamond"],
        "before_phase": before["phase"],
        "after_phase": after["phase"],
        "after_proof_success": after.get("proof_success"),
        "after_model_audit_ok": after.get("model_audit_ok"),
        "after_success": after["success"],
        "after_judge_ok": after.get("judge_ok"),
        "before_failure_family": before.get("failure_family", ""),
        "after_failure_family": after.get("failure_family", ""),
        "before_branch_id": before.get("branch_id", "main"),
        "after_branch_id": after.get("branch_id", "main"),
        "after_branch_focus": after.get("branch_focus", ""),
        "after_parent_iteration": after.get("parent_iteration"),
        "source": "long_ralph",
        "repair_generator": after["generator"],
    }


def build_repair_context(verdict: dict, steps: list[dict]) -> str:
    lines = [
        "Previous candidate did not pass the full Ralph gate.",
        (
            f"Last result: tier={verdict['tier']} phase={verdict['phase']} "
            f"score={verdict['score']:.3f} diamond={verdict['diamond']} "
            f"judge_ok={verdict.get('judge_ok')} "
            f"failure_family={classify_failure_family(verdict)}"
        ),
    ]

    if verdict["phase"] == "adequacy" and verdict.get("judge_reason"):
        lines.append(f"Final model verifier rejection: {verdict['judge_reason']}")
        lines.append("The previous spec passed SANY/TLC, so repair the model meaning, not only syntax.")
    elif verdict.get("diagnostics"):
        lines.append(f"Verifier diagnostics: {verdict['diagnostics']}")

    spec = (steps[-1].get("spec") or "") if steps else ""
    excerpt = line_numbered_error_excerpt(spec, verdict.get("diagnostics", ""))
    if excerpt:
        lines.append("Line-numbered excerpt around the reported error:")
        lines.append(excerpt)

    syntax_hint = syntax_repair_hint(spec, verdict.get("diagnostics", ""))
    if syntax_hint:
        lines.append(syntax_hint)

    shape_hint = spec_shape_hint(spec, verdict)
    if shape_hint:
        lines.append(shape_hint)

    semantic_hint = semantic_repair_hint(verdict)
    if semantic_hint:
        lines.append(semantic_hint)

    stuck = stuck_rewrite_instruction(steps)
    if stuck:
        lines.append(stuck)

    semantic = verdict.get("semantic") or {}
    if semantic:
        lines.append(f"Semantic verifier summary: {json.dumps(semantic, sort_keys=True)[:1400]}")

    recent = steps[-6:]
    if recent:
        lines.append("Recent attempts:")
        for item in recent:
            reason = item.get("judge_reason") or item.get("diagnostics") or ""
            lines.append(
                f"- iter {item['iteration']}: tier={item['tier']} phase={item['phase']} "
                f"score={item['score']:.3f} judge_ok={item.get('judge_ok')} "
                f"reason={_compact(reason, 180)}"
            )

    return _trim_context("\n".join(lines), limit=5000)


def line_numbered_error_excerpt(spec: str, diagnostics: str, radius: int = 8) -> str:
    lines = (spec or "").splitlines()
    if not lines:
        return ""

    line_numbers = [
        int(match.group(1))
        for match in re.finditer(r"\bline\s+(\d+)\b", diagnostics or "", flags=re.IGNORECASE)
    ]
    if not line_numbers:
        return ""

    line_no = max(1, min(line_numbers[0], len(lines)))
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(f"{i:04d}: {lines[i - 1]}" for i in range(start, end + 1))


def stuck_rewrite_instruction(steps: list[dict], tail_limit: int = 4) -> str:
    if len(steps) < tail_limit:
        return ""

    tail = steps[-tail_limit:]
    same_spec = all((item.get("spec_hash") or "") == (tail[-1].get("spec_hash") or "") for item in tail)
    same_failure = all(
        (item.get("failure_signature") or "") == (tail[-1].get("failure_signature") or "")
        for item in tail
    )
    if not same_spec and not same_failure:
        return ""

    phase = tail[-1].get("phase")
    if phase == "sany":
        return (
            "STUCK SYNTAX REWRITE MODE: the recent attempts are repeating the same parse failure "
            "or unchanged spec. Do not preserve the broken structure. Rewrite a smaller complete "
            "module from scratch, or fully replace the broken helper/action. Every IF expression "
            "must include THEN and ELSE. Avoid custom recursive helper operators unless they are "
            "fully defined and SANY-simple."
        )
    if phase == "adequacy":
        return (
            "STUCK ADEQUACY REWRITE MODE: recent TLC-passing specs are still being rejected by the "
            "model verifier. Make a semantic change, not a rename. Add the missing actions, actors, "
            "state variables, fairness, or liveness property named by the judge."
        )
    return ""


def syntax_repair_hint(spec: str, diagnostics: str) -> str:
    diagnostics = diagnostics or ""
    hints = []
    if "Assumption line" in diagnostics or "Evaluating assumption" in diagnostics:
        hints.append(
            "TLC assumption hint: the generated model has a false or unevaluable ASSUME. "
            "For this benchmark, prefer concrete finite definitions instead of CONSTANTS plus ASSUME. "
            "Use forms like Proc == 1..3 and MaxWaiters == 2, then remove the ASSUME lines."
        )
    if "Precedence conflict between ops" in diagnostics:
        hints.append(
            "TLA+ precedence hint: avoid mixing /\\ and \\/ inline. Rewrite actions as block-structured "
            "guarded disjunctions where each case starts with `\\/ /\\ guard` and every following update "
            "line starts with `/\\`. Do not write one-line expressions like "
            "`/\\ (guard /\\ update) \\/ (guard2 /\\ update2)`."
        )
    if "Unknown operator: `Cardinality'" in diagnostics or "Unknown operator: 'Cardinality'" in diagnostics:
        hints.append(
            "TLA+ module hint: Cardinality is defined by FiniteSets. Add `FiniteSets` to EXTENDS, "
            "or avoid Cardinality by writing invariants with quantifiers, e.g. "
            "`AtMostOneHolder == \\A p, q \\in Proc : (pc[p] = \"holding\" /\\ pc[q] = \"holding\") => p = q`."
        )
    if "The operator Range requires 0 arguments" in diagnostics:
        hints.append(
            "TLA+ sequence hint: Range is not a sequence-to-set function in TLC. To test whether "
            "`p` appears in a sequence such as `waiters`, use "
            "`\\E i \\in 1..Len(waiters) : waiters[i] = p`, or model waiters as a set when order "
            "does not matter."
        )
    if "IF THEN ELSE" in diagnostics:
        hints.append(
            "TLA+ syntax hint: this parse failure is inside an IF expression. Every IF must have "
            "both THEN and ELSE. For action definitions, avoid IF and write guarded disjuncts instead:\n"
            "Action ==\n"
            "  \\\\/ /\\\\ guard_case_1\n"
            "     /\\\\ x' = new_x\n"
            "     /\\\\ UNCHANGED y\n"
            "  \\\\/ /\\\\ guard_case_2\n"
            "     /\\\\ y' = new_y\n"
            "     /\\\\ UNCHANGED x\n"
            "Do not write `IF condition THEN /\\\\ update`; that commonly leaves an incomplete action."
        )
    if "Ill-structured fairness expression" in diagnostics or "operator $WF" in diagnostics:
        hints.append(
            "TLA+ fairness syntax hint: weak fairness is written as WF_vars(ActionName), "
            "where vars is the tuple variable defined by vars == <<...>>. Do not invent names "
            "like WF_ActionName, and do not call WF_ActionName(ActionName). A safe form is "
            "Spec == Init /\\\\ [][Next]_vars /\\\\ WF_vars(Next)."
        )
    return "\n\n".join(hints)


def classify_failure_family(verdict: dict) -> str:
    if verdict.get("success"):
        return "success"

    phase = verdict.get("phase") or ""
    text = " ".join([
        str(verdict.get("judge_reason") or ""),
        str(verdict.get("diagnostics") or ""),
    ]).lower()
    semantic = verdict.get("semantic") or {}

    if phase == "sany":
        if "precedence conflict" in text:
            return "syntax_precedence"
        if "unknown operator" in text:
            return "syntax_unknown_operator"
        if "fairness expression" in text or "operator $wf" in text:
            return "syntax_fairness"
        if "if then else" in text:
            return "syntax_if_then_else"
        return "syntax"

    if phase == "tlc":
        if "assumption line" in text or "evaluating assumption" in text:
            return "false_assumption"
        if (
            "temporal properties were violated" in text
            or "liveness" in text
            or re.search(r"\bproperty\b[^\n.]*violat", text)
        ):
            return "property_violation"
        return "tlc"

    if phase == "adequacy":
        properties_declared = bool(semantic.get("properties_declared"))
        properties_checked = int(semantic.get("properties_checked") or 0)
        if (
            ("properties" in text or "liveness" in text)
            and ("not instructed" in text or "not include" in text or "not checked" in text)
        ) or (properties_declared and properties_checked == 0):
            return "declared_but_unchecked_liveness"
        if any(token in text for token in ("release", "holder", "ownership")):
            return "bad_ownership"
        if any(token in text for token in ("liveness", "fairness", "waiting", "eventually", "progress", "starv")):
            return "weak_fairness"
        if int(semantic.get("distinct_states") or 0) <= 1 or any(
            token in text for token in ("vacuous", "too strong", "overly strong")
        ):
            return "vacuous_safety"
        if int(semantic.get("total_actions") or 0) == 0 or float(semantic.get("action_coverage") or 0.0) == 0.0:
            return "zero_action_coverage"
        return "adequacy"

    if verdict.get("malformed"):
        return "malformed"
    return phase or "unknown"


def same_failure_family_tail_count(steps: list[dict]) -> int:
    if not steps:
        return 0
    family = steps[-1].get("failure_family")
    if not family:
        return 0
    count = 0
    for step in reversed(steps):
        if step.get("failure_family") != family:
            break
        count += 1
    return count


def should_stop_for_semantic_stall(steps: list[dict], args: argparse.Namespace) -> bool:
    if not args.semantic_stall_stop or args.max_same_failure_family_iters <= 0 or not steps:
        return False
    last = steps[-1]
    if last.get("success") or last.get("phase") != "adequacy":
        return False
    family = last.get("failure_family") or ""
    if family in {"success", "malformed", "syntax", "tlc"}:
        return False
    return same_failure_family_tail_count(steps) >= args.max_same_failure_family_iters


def should_stop_for_frontier_stall(steps: list[dict], args: argparse.Namespace) -> bool:
    if args.max_frontier_stall_iters <= 0 or not steps:
        return False
    if steps[-1].get("success"):
        return False
    return frontier_stall_count(steps) >= args.max_frontier_stall_iters


def summarize_trajectory(traj: dict) -> dict:
    steps = traj.get("steps") or []
    families = Counter(step.get("failure_family") or "unknown" for step in steps)
    branch_steps = [step for step in steps if step.get("branch_id") not in {"", None, "main"}]
    branch_rounds = {
        match.group(1)
        for step in branch_steps
        for match in [re.match(r"r(\d+)b\d+", str(step.get("branch_id", "")))]
        if match
    }
    last = steps[-1] if steps else {}
    semantic = last.get("semantic") or {}
    return {
        "failure_families": dict(families),
        "last_failure_family": last.get("failure_family", ""),
        "semantic_stall_count": same_failure_family_tail_count(steps),
        "frontier_stall_count": frontier_stall_count(steps),
        "branch_steps": len(branch_steps),
        "branch_rounds": len(branch_rounds),
        "properties_checked": int(semantic.get("properties_checked") or 0),
        "properties_declared": bool(semantic.get("properties_declared")),
        "property_names": semantic.get("property_names") or [],
    }


def aggregate_failure_families(rows: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(row.get("failure_families") or {})
    return dict(counts)


def write_run_report(path: Path, summaries: list[dict]) -> None:
    report = {
        "created_at": int(time.time()),
        "num_trajectories": len(summaries),
        "num_success": sum(1 for row in summaries if row.get("success")),
        "failure_families": aggregate_failure_families(summaries),
        "rows": summaries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def spec_shape_hint(spec: str, verdict: dict) -> str:
    hints = []
    if re.search(r"^\s*CONSTANTS?\b", spec or "", re.MULTILINE) and re.search(
        r"^\s*ASSUME\b", spec or "", re.MULTILINE
    ):
        hints.append(
            "Model-shape hint: avoid CONSTANTS + ASSUME for small benchmark domains. "
            "Replace them with concrete operators before VARIABLES, such as `Proc == 1..3` "
            "and `MaxWaiters == 2`. This prevents TLC auto-config from choosing values that "
            "make assumptions false."
        )

    if re.search(r"^\s*SpecWithFairness\s*==", spec or "", re.MULTILINE):
        hints.append(
            "Spec-shape hint: do not define an unused `SpecWithFairness`. Put fairness directly "
            "in `Spec == Init /\\ [][Next]_vars /\\ WF_vars(Next)` because the auto-generated TLC "
            "config checks `SPECIFICATION Spec`."
        )

    duplicate_assignments = branch_assignment_conflicts(spec)
    if duplicate_assignments:
        hints.append(
            "Action-shape hint: some action bodies appear to both update and UNCHANGED the same "
            f"variables ({', '.join(sorted(duplicate_assignments))}). In TLA+, every action branch "
            "must assign each variable exactly once. Move UNCHANGED into only the branches where "
            "that variable is not primed."
        )

    return "\n".join(hints)


def branch_assignment_conflicts(spec: str) -> set[str]:
    conflicts: set[str] = set()
    current: list[str] = []
    for line in (spec or "").splitlines():
        if re.match(r"^\s*[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", line):
            _collect_assignment_conflicts(current, conflicts)
            current = [line]
        else:
            current.append(line)
    _collect_assignment_conflicts(current, conflicts)
    return conflicts


def _collect_assignment_conflicts(lines: list[str], conflicts: set[str]) -> None:
    for branch in _action_branches(lines):
        text = "\n".join(branch)
        primed = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*'", text))
        for match in re.finditer(r"UNCHANGED\s+(?:<<([^>]*)>>|([A-Za-z_][A-Za-z0-9_]*))", text):
            raw = match.group(1) or match.group(2) or ""
            for name in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", raw):
                if name in primed:
                    conflicts.add(name)


def _action_branches(lines: list[str]) -> list[list[str]]:
    branches: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if re.match(r"^\s*\\/", line) and current:
            branches.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        branches.append(current)
    return branches


def semantic_repair_hint(verdict: dict) -> str:
    if verdict.get("phase") != "adequacy":
        return ""
    reason = (verdict.get("judge_reason") or verdict.get("diagnostics") or "").lower()
    semantic = verdict.get("semantic") or {}
    hints = []
    if int(semantic.get("distinct_states") or 0) <= 1:
        hints.append(
            "Diamond hint: the model appears vacuous or static. Add real state-changing actions "
            "with enabled guards, such as P(p) changing an idle process to waiting/holding and V(p) "
            "releasing or waking a waiter. Avoid a Next relation that only stutters."
        )
    if int(semantic.get("total_actions") or 0) == 0 or float(semantic.get("action_coverage") or 0.0) == 0.0:
        hints.append(
            "Action-coverage hint: define named action operators and include them directly in Next, "
            "for example Next == \\E p \\in Proc : P(p) \\/ V(p)."
        )
    if any(word in reason for word in ("liveness", "fairness", "progress", "eventually", "eventual")):
        hints.append(
            "Adequacy hint: add an explicit liveness/progress property and put real TLA+ fairness "
            "in Spec using WF_vars(ActionName) or WF_vars(Next). If you define a separate temporal "
            "property such as WaitersEventuallyHold, it must be checkable by TLC through PROPERTY "
            "configuration or implied by Spec. Do not use fake operators like WF_ActionName."
        )
    if any(word in reason for word in ("vacuous", "too strong", "overly strong", "does not accurately model")):
        hints.append(
            "Adequacy hint: do not make safety true by over-restricting enabled behavior. The model "
            "must still allow realistic contention, blocking, waiting, release, and wakeup paths; "
            "the invariant should be checked against those behaviors, not made vacuous by guards."
        )
    if any(word in reason for word in ("release", "holder", "holding")):
        hints.append(
            "Ownership hint: release actions should require the releasing process to be the current "
            "holder, e.g. `V(p) == /\\ pc[p] = \"holding\" /\\ holder = p ...`. Wakeup should happen "
            "as part of release semantics, not as an unconstrained spontaneous transition."
        )
    if any(word in reason for word in ("process", "actor", "waiter", "waiting")):
        hints.append(
            "Modeling hint: if the judge asks for explicit process behavior, introduce a finite "
            "process set such as Proc or 1..N and model per-process state, for example "
            "pc \\in [Proc -> {\"idle\", \"waiting\", \"holding\"}], with actions P(p) and V(p)."
        )
    return "\n".join(hints)


def model_recipe(description: str, module: str, diagnostics: str) -> str:
    text = " ".join([description or "", module or "", diagnostics or ""]).lower()
    if "semaphore" in text:
        return (
            "Semaphore modeling recipe:\n"
            "- Avoid CONSTANTS/ASSUME; define `Proc == 1..3` and `MaxWaiters == 2` as operators.\n"
            "- Use `pc \\in [Proc -> {\"idle\", \"waiting\", \"holding\"}]` and optionally a FIFO queue.\n"
            "- `P(p)` should branch: acquire only when no holder/no priority waiter; otherwise move p to waiting.\n"
            "- `V(p)` must require `pc[p] = \"holding\"` and, if tracking owner, `holder = p`.\n"
            "- Waking a waiter should be part of V/release semantics, not a free spontaneous transition.\n"
            "- `Spec` should include fairness directly, e.g. `Spec == Init /\\ [][Next]_vars /\\ WF_vars(Next)`.\n"
            "- Prefer quantified safety over Cardinality unless `EXTENDS FiniteSets` is present.\n"
            "- Put every invariant/property that matters as named operators; do not rely on prose comments."
        )
    if any(word in text for word in ("lock", "mutex", "spinlock", "ticketlock")):
        return (
            "Lock modeling recipe:\n"
            "- Define a finite `Thread == 1..3` or `Proc == 1..3` operator instead of constants/assumptions.\n"
            "- Track per-thread state with `pc \\in [Thread -> {...}]` plus lock/owner variables.\n"
            "- Model separate Acquire(t) and Release(t) actions, and include them directly in `Next`.\n"
            "- Use `Spec == Init /\\ [][Next]_vars /\\ WF_vars(Next)` if progress/fairness is required."
        )
    if any(word in text for word in ("queue", "fifo")):
        return (
            "Queue modeling recipe:\n"
            "- Use bounded sequences with concrete bounds, e.g. `MaxLen == 3`.\n"
            "- Define Enqueue/Dequeue as guarded action operators included directly in `Next`.\n"
            "- Avoid custom recursive sequence helpers unless absolutely necessary."
        )
    return ""


def save_accepted_spec(traj: dict, accepted_dir: Path) -> Path | None:
    if not traj.get("success"):
        return None
    steps = traj.get("steps") or []
    if not steps:
        return None

    final = steps[-1]
    spec = (final.get("spec") or "").strip()
    if not spec:
        return None

    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", traj["prompt_id"]).strip("_")
    spec_path = accepted_dir / f"{safe_id}.tla"
    meta_path = accepted_dir / f"{safe_id}.json"
    spec_path.write_text(spec + "\n", encoding="utf-8")
    meta_path.write_text(json.dumps({
        "prompt_id": traj["prompt_id"],
        "module_name": traj["module_name"],
        "domain": traj["domain"],
        "iterations": traj["iterations"],
        "stop_reason": traj["stop_reason"],
        "final_score": final["score"],
        "final_tier": final["tier"],
        "final_phase": final["phase"],
        "proof_success": final.get("proof_success"),
        "model_audit_ok": final.get("model_audit_ok"),
        "model_audit_reason": final.get("model_audit_reason", ""),
        "judge_ok": final.get("judge_ok"),
        "frozen_properties": traj.get("frozen_properties", ""),
        "semantic": final.get("semantic", {}),
    }, indent=2) + "\n", encoding="utf-8")
    return spec_path


def audit_candidate(
    description: str,
    frozen: str,
    spec: str,
    semantic: dict,
) -> tuple[bool, str]:
    """Deterministic modeling audit before the optional LLM adequacy judge."""
    requirement = _with_frozen(description, frozen).lower()
    spec_text = spec or ""
    semantic = semantic or {}

    if int(semantic.get("distinct_states") or 0) <= 1:
        return False, "Local modeling audit: reachable state space is static or nearly static."
    if int(semantic.get("invariants_checked") or 0) <= 0:
        return False, "Local modeling audit: no safety invariant is checked by TLC."
    if bool(semantic.get("trivial_invariant")):
        return False, "Local modeling audit: checked invariant appears trivial or vacuous."
    if bool(semantic.get("mutation_tested")) and not bool(semantic.get("mutation_caught")):
        return False, "Local modeling audit: invariants did not catch the mutation test."

    if _requirement_needs_liveness(requirement):
        if int(semantic.get("properties_checked") or 0) <= 0:
            return (
                False,
                "Local modeling audit: requirement asks for waiting/progress/liveness, "
                "but no temporal property is checked by TLC.",
            )
        if not re.search(r"\b[WS]F_", spec_text):
            return (
                False,
                "Local modeling audit: requirement asks for progress, but Spec has no WF_/SF_ fairness.",
            )

    missing = _missing_requirement_model_tokens(requirement, spec_text)
    if missing:
        return False, f"Local modeling audit: missing explicit model element for {missing}."

    return True, ""


def _requirement_needs_liveness(requirement: str) -> bool:
    return any(
        token in requirement
        for token in (
            "wait", "waiting", "blocked", "blocks", "eventual", "eventually",
            "progress", "liveness", "fairness", "starv", "terminate", "proceed",
        )
    )


def _missing_requirement_model_tokens(requirement: str, spec: str) -> str:
    checks = [
        ("waiter/waiting state", ("wait", "blocked", "blocks", "queue", "fifo"), r"(?i)\b(wait|queue|fifo|pc)\b"),
        ("reader state", ("reader", "readers"), r"(?i)\breader"),
        ("writer state", ("writer", "writers"), r"(?i)\bwriter"),
        ("acquire/P action", ("acquire", " p()", " p operation"), r"(?i)\b(Acquire|P)\s*\(?"),
        ("release/V action", ("release", " v()", " v operation"), r"(?i)\b(Release|V)\s*\(?"),
    ]
    for label, requirement_tokens, spec_pattern in checks:
        if any(token in requirement for token in requirement_tokens) and not re.search(spec_pattern, spec):
            return label
    return ""


def freeze_properties(teacher: OllamaCloud, description: str) -> str:
    try:
        raw = teacher.review([
            {"role": "system", "content": FREEZE_SYSTEM},
            {"role": "user", "content": description},
        ])
    except Exception as exc:
        print(f"  property-freeze skipped: {exc}")
        return ""
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*==", stripped) and _state_level_property(stripped):
            lines.append(line)
    return "\n".join(lines).strip()


def judge_candidate(
    teacher: OllamaCloud,
    description: str,
    frozen: str,
    spec: str,
    semantic: dict,
) -> tuple[bool, str]:
    try:
        raw = teacher.review([
            {"role": "system", "content": JUDGE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Requirement:\n{_with_frozen(description, frozen)}\n\n"
                    f"Semantic verifier summary:\n{json.dumps(semantic, sort_keys=True)[:3000]}\n\n"
                    f"Candidate spec:\n```tla\n{spec}\n```\n"
                ),
            },
        ])
    except Exception as exc:
        return False, f"Final adequacy judge failed: {exc}"
    return parse_judge_response(raw)


def parse_judge_response(text: str) -> tuple[bool, str]:
    cleaned = (text or "").strip()
    first = cleaned.splitlines()[0].strip() if cleaned else ""
    if first == "OK":
        return True, ""
    if first.startswith("NOT_OK:"):
        reason = first[len("NOT_OK:"):].strip()
        return False, reason or "Final adequacy judge rejected the spec."
    return False, f"Final adequacy judge returned ambiguous response: {cleaned[:500]}"


def _repair_user(
    description: str,
    module: str,
    previous_spec: str,
    diagnostics: str,
    iteration: int,
    frozen: str,
) -> str:
    return (
        f"Repair iteration {iteration}. Use module name {module}.\n\n"
        f"Original requirement:\n{_with_frozen(description, frozen)}\n\n"
        f"{model_recipe(description, module, diagnostics)}\n\n"
        f"Previous spec:\n{previous_spec}\n\n"
        f"Verifier / model-checker feedback:\n{diagnostics}\n\n"
        "Do not return the previous spec unchanged. "
        "If the feedback says STUCK SYNTAX REWRITE MODE, prefer a fresh simpler module over local edits. "
        "If the feedback includes a line-numbered excerpt, fix that exact region or remove the broken construct. "
        "Return a corrected complete pure-TLA+ module only. "
        "Fix the diagnostics without weakening the requirement."
    )


def _repair_diff_user(
    description: str,
    module: str,
    previous_spec: str,
    diagnostics: str,
    iteration: int,
    frozen: str,
) -> str:
    return (
        f"Repair iteration {iteration}. Use module name {module}.\n\n"
        f"Original requirement:\n{_with_frozen(description, frozen)}\n\n"
        f"{model_recipe(description, module, diagnostics)}\n\n"
        f"Previous spec:\n{previous_spec}\n\n"
        f"Verifier / model-checker feedback:\n{diagnostics}\n\n"
        "Return a unified diff patch against the previous spec. "
        "Make the smallest decisive edit that fixes the reported issue. "
        "Do not return prose. Do not return the full module unless it is represented as diff hunks. "
        "If the feedback says STUCK SYNTAX REWRITE MODE, the diff may replace large regions, but it must still be a valid unified diff."
    )


def _extract_unified_diff(text: str) -> str:
    if not text:
        return ""

    fenced = re.search(r"```(?:diff)?\n(.*?)```", text, flags=re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    candidate = candidate.strip()
    lines = candidate.splitlines()

    start = None
    for idx, line in enumerate(lines):
        if line.startswith("--- ") or line.startswith("@@ "):
            start = idx
            break
    if start is None:
        return ""
    return "\n".join(lines[start:]).strip()


def _apply_unified_diff(original: str, diff_text: str) -> str:
    diff_lines = [line.rstrip("\n") for line in (diff_text or "").splitlines()]
    if not diff_lines:
        raise ValueError("empty diff")

    idx = 0
    while idx < len(diff_lines) and not diff_lines[idx].startswith("@@ "):
        idx += 1
    if idx >= len(diff_lines):
        raise ValueError("diff contains no hunks")

    original_lines = original.splitlines()
    output: list[str] = []
    source_index = 0

    while idx < len(diff_lines):
        header = diff_lines[idx]
        match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)$", header)
        if not match:
            raise ValueError(f"invalid hunk header: {header}")
        old_start = int(match.group(1))
        idx += 1

        target_index = old_start - 1
        if target_index < source_index or target_index > len(original_lines):
            raise ValueError("hunk out of range")
        output.extend(original_lines[source_index:target_index])
        source_index = target_index

        while idx < len(diff_lines) and not diff_lines[idx].startswith("@@ "):
            line = diff_lines[idx]
            if line == r"\ No newline at end of file":
                idx += 1
                continue
            if not line:
                prefix = " "
                payload = ""
            else:
                prefix = line[0]
                payload = line[1:]
            if prefix == " ":
                if source_index >= len(original_lines) or original_lines[source_index] != payload:
                    raise ValueError("context mismatch")
                output.append(payload)
                source_index += 1
            elif prefix == "-":
                if source_index >= len(original_lines) or original_lines[source_index] != payload:
                    raise ValueError("remove mismatch")
                source_index += 1
            elif prefix == "+":
                output.append(payload)
            else:
                raise ValueError(f"unexpected diff line: {line}")
            idx += 1

    output.extend(original_lines[source_index:])
    return "\n".join(output)


def _patched_spec_from_response(previous_spec: str, response: str) -> str | None:
    diff = _extract_unified_diff(response)
    if not diff:
        return None
    try:
        patched = _apply_unified_diff(previous_spec, diff)
    except ValueError:
        return None
    patched = patched.strip()
    if not patched or patched == previous_spec.strip():
        return None
    return patched


def _append_jsonl(path_arg: str, row: dict) -> None:
    path = _abs(path_arg)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _validator_diagnostics(errors: list[str], raw_output: str, limit: int = 3000) -> str:
    rendered_errors = "\n".join(errors).strip()
    rendered_raw = (raw_output or "").strip()
    if rendered_errors:
        if len(rendered_errors) >= limit:
            return rendered_errors[:limit]
        parts = [rendered_errors]
        raw_budget = limit - len(rendered_errors) - 2
        if raw_budget > 0 and rendered_raw and rendered_raw not in rendered_errors:
            parts.append(rendered_raw[-raw_budget:])
        return "\n\n".join(parts) or "Validator failed without diagnostics."
    if rendered_raw:
        return rendered_raw[-limit:]
    return "Validator failed without diagnostics."


def _trim_context(text: str, limit: int = 5000) -> str:
    if len(text) <= limit:
        return text
    marker = "\n...[truncated]...\n"
    head_len = min(1800, max(0, limit // 2))
    tail_len = max(0, limit - head_len - len(marker))
    return text[:head_len].rstrip() + marker + text[-tail_len:].lstrip()


def _state_level_property(line: str) -> bool:
    forbidden = ("[]", "<>", "WF_", "SF_", "ENABLED", "'")
    return not any(token in line for token in forbidden)


def _judge_status(verdict: dict) -> str:
    parts = []
    if verdict.get("model_audit_ok") is True:
        parts.append("audit=ok")
    elif verdict.get("model_audit_ok") is False:
        parts.append("audit=reject")
    if verdict.get("judge_ok") is True:
        parts.append("judge=ok")
    elif verdict.get("judge_ok") is False:
        parts.append("judge=reject")
    return f" {' '.join(parts)}" if parts else ""


def _compact(text: str, limit: int) -> str:
    compacted = " ".join((text or "").split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: max(0, limit - 3)] + "..."


def _with_frozen(description: str, frozen: str) -> str:
    if not frozen:
        return description
    return (
        f"{description}\n\nRequired property operators to preserve and check:\n"
        f"{frozen}"
    )


def _semantic_gap(semantic) -> str:
    details = (
        "TLC passed, but the stronger diamond/adequacy gate failed. "
        f"distinct_states={semantic.distinct_states}; "
        f"invariants_checked={semantic.invariants_checked}; "
        f"trivial_invariant={semantic.trivial_invariant}; "
        f"mutation_tested={semantic.mutation_tested}; "
        f"mutation_caught={semantic.mutation_caught}. "
    )
    if semantic.distinct_states <= 1:
        return (
            details
            + " The reachable model is static or nearly static; add enabled state-changing actions "
            "and avoid a Next relation that only stutters."
        )
    if semantic.total_actions == 0 or semantic.action_coverage == 0:
        return (
            details
            + " No named actions were covered; define concrete action operators and include them in Next."
        )
    return details + " Strengthen the checked safety invariant and avoid a thin or vacuous model."


def _module_name(spec: str) -> str:
    m = re.search(r"----\s*MODULE\s+([A-Za-z_][A-Za-z0-9_]*)", spec or "")
    return m.group(1) if m else ""


def _abs(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else _REPO_ROOT / p


if __name__ == "__main__":
    raise SystemExit(main())
