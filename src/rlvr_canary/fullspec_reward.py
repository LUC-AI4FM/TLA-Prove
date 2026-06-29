"""Full-spec component-weighted reward for GRPO training on TLA+.

Unlike the per-action reward (tla_reward.py) which grades only the Next
operator fragment, this reward function evaluates complete TLA+ specs against
the 7-component partial credit signal from component_validator:

  init_present        0.05
  next_present        0.05
  init_level_ok       0.10
  next_level_ok       0.10
  invariants_declared 0.10
  tlc_depth1_ok       0.25
  tlc_full_ok         0.35

This gives ~10 distinct reward levels in [0, 1], solving the zero-variance
problem that killed the per-action 20B GRPO run (where all 8 completions
got the same tier → zero GRPO advantage → zero gradient).

Speed: ~55s worst case per completion (SANY 10s + depth-1 15s + full TLC 30s).
With ThreadPoolExecutor(4), 4 completions take ~55s wall time per GRPO step.
"""

from __future__ import annotations

import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from src.validators.component_validator import reward_from_spec


_REWARD_WORKERS = int(os.environ.get("CHATTLA_REWARD_WORKERS", "4"))
_FULL_TLC_TIMEOUT = int(os.environ.get("CHATTLA_REWARD_TLC_TIMEOUT", "30"))
_SAMPLE_LOG_LOCK = threading.Lock()
_SAMPLE_LOG_CALL = 0
_OP_DEF_RE = re.compile(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*==")
_MODULE_RE = re.compile(r"----\s*MODULE\s+([A-Za-z_][A-Za-z0-9_]*)")
_TARGET_MODULE_RE = re.compile(
    r"(?:module\s+name\s+exactly|module\s+named)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def _completion_text(comp: Any) -> str:
    """Normalize TRL's two completion shapes (string vs message list)."""
    if isinstance(comp, list):
        return "".join(m.get("content", "") for m in comp if isinstance(m, dict))
    return str(comp or "")


def _prompt_text(prompt: Any) -> str:
    """Normalize TRL prompt shapes for target extraction."""
    if isinstance(prompt, list):
        return "\n".join(m.get("content", "") for m in prompt if isinstance(m, dict))
    return str(prompt or "")


def _target_module_from_prompt(prompt: Any) -> str | None:
    match = _TARGET_MODULE_RE.search(_prompt_text(prompt))
    return match.group(1) if match else None


def _module_name(text: str) -> str | None:
    match = _MODULE_RE.search(text or "")
    return match.group(1) if match else None


def _operator_body(text: str, name: str) -> str:
    """Best-effort raw body extraction for cheap pre-SANY heuristics."""
    match = re.search(rf"(?m)^{re.escape(name)}\s*==", text)
    if not match:
        return ""
    next_match = _OP_DEF_RE.search(text, match.end())
    end = next_match.start() if next_match else len(text)
    return text[match.end():end]


def _declaration_blocks(text: str) -> list[tuple[str, str]]:
    """Return CONSTANT/VARIABLE declaration blocks before the next operator."""
    blocks: list[tuple[str, str]] = []
    for match in re.finditer(r"(?m)^(CONSTANTS?|VARIABLES?)\b", text):
        next_op = _OP_DEF_RE.search(text, match.end())
        next_decl = re.search(r"(?m)^(CONSTANTS?|VARIABLES?|EXTENDS)\b", text[match.end():])
        candidates = [len(text)]
        if next_op:
            candidates.append(next_op.start())
        if next_decl:
            candidates.append(match.end() + next_decl.start())
        block = text[match.end():min(candidates)]
        blocks.append((match.group(1).upper(), block))
    return blocks


def _forward_reference_issues(text: str) -> list[str]:
    """Detect helper operators that are used by Next before they are defined."""
    issues: list[str] = []
    next_match = re.search(r"(?m)^Next\s*==", text)
    if not next_match:
        return issues
    next_body = _operator_body(text, "Next")
    for op_match in _OP_DEF_RE.finditer(text):
        name = op_match.group(1)
        if name in {"Init", "Next"}:
            continue
        if op_match.start() <= next_match.start():
            continue
        if re.search(rf"\b{re.escape(name)}\b", next_body):
            issues.append(f"forward_reference_{name.lower()}")
    return sorted(set(issues))


def _syntax_hygiene_issues(text: str) -> list[str]:
    """Cheap, high-precision markers for common SANY/TLC-invalid patterns."""
    issues: list[str] = []
    decl_blocks = _declaration_blocks(text)
    for kind, block in decl_blocks:
        if "\\in" in block or "->" in block:
            issues.append(f"typed_{kind.lower()}")
        if kind.startswith("CONSTANT") and re.search(r"(?<![<>=#])=(?![=>])", block):
            issues.append("constant_assignment")

    init_body = _operator_body(text, "Init")
    if re.search(r"\b[A-Za-z_][A-Za-z0-9_]*'", init_body):
        issues.append("primed_init")

    next_body = _operator_body(text, "Next")
    if re.search(r"(?m)^\s*(?:/\\|\\/)\s*[A-Za-z_][A-Za-z0-9_]*\s*==", next_body):
        issues.append("nested_operator_in_next")

    pattern_issues = [
        ("empty_unchanged", r"UNCHANGED\s*<<\s*>>"),
        ("lowercase_len", r"\blen\s*\("),
        ("bad_sequence_helper", r"\b(?:SeqHead|SeqTail)\s*\("),
        ("invalid_implies_token", r"\\implies\b"),
        ("pseudo_predicate_name", r"\b[A-Za-z_][A-Za-z0-9_]*\?"),
        ("string_type_constant", r"\bSTRING\b"),
    ]
    for issue, pattern in pattern_issues:
        if re.search(pattern, text):
            issues.append(issue)

    issues.extend(_forward_reference_issues(text))

    return sorted(set(issues))


def _structural_floor(text: str) -> float:
    """Cheap pre-SANY reward for full-module shape.

    The component validator is intentionally verifier-driven, but early GRPO
    can otherwise see a flat zero for near-miss modules that SANY rejects. This
    floor keeps those attempts distinguishable without letting structure alone
    compete with parse/depth/TLC success.
    """
    if not text or not text.strip():
        return 0.0
    score = 0.0
    stripped = text.lstrip()
    if stripped.startswith("---- MODULE"):
        score += 0.025
    if "====" in text:
        score += 0.015
    if "EXTENDS" in text:
        score += 0.015
    if "VARIABLE" in text:
        score += 0.025
    if re.search(r"(?m)^Init\s*==", text):
        score += 0.035
    if re.search(r"(?m)^Next\s*==", text):
        score += 0.035
    if re.search(r"(?m)^Spec\s*==", text):
        score += 0.025
    if re.search(r"(?m)^(TypeOK|TypeInvariant|Safety|Invariant|Inv\w*)\s*==", text):
        score += 0.025

    # Syntax hygiene bonuses inside the pre-SANY band. These make common
    # near-miss classes separable while keeping all verifier-passing rewards
    # above this floor.
    decl_blocks = _declaration_blocks(text)
    typed_decl = any("\\in" in block or "->" in block for _kind, block in decl_blocks)
    if not typed_decl:
        score += 0.035
    if "EXISTS" not in text:
        score += 0.02
    if "#=" not in text and ":=" not in text:
        score += 0.015
    if re.search(r"(?m)^vars\s*==\s*<<", text) or "_<<" in text or "]_vars" in text:
        score += 0.015

    issues = _syntax_hygiene_issues(text)
    if issues:
        score -= min(0.10, 0.015 * len(issues))
    critical = {
        "typed_constants",
        "typed_constant",
        "typed_variables",
        "typed_variable",
        "empty_unchanged",
        "constant_assignment",
        "nested_operator_in_next",
        "primed_init",
    }
    if any(issue in critical for issue in issues):
        score = min(score, 0.18)
    return min(score, 0.28)


def _module_match_cap(text: str, target_module: str | None) -> float | None:
    if not target_module:
        return None
    produced = _module_name(text)
    if produced == target_module:
        return None
    return 0.32


def _grade_one(text: str, target_module: str | None = None) -> float:
    """Grade a single completion via the component validator."""
    if not text or not text.strip():
        return 0.0
    floor = _structural_floor(text)
    issues = _syntax_hygiene_issues(text)
    if any(issue.startswith("forward_reference_") for issue in issues):
        floor = min(floor, 0.14)
    module_cap = _module_match_cap(text, target_module)
    critical_issues = {
        "typed_constants",
        "typed_constant",
        "typed_variables",
        "typed_variable",
        "empty_unchanged",
        "constant_assignment",
        "nested_operator_in_next",
        "primed_init",
    }
    try:
        component = reward_from_spec(
            text,
            run_depth1=True,
            run_full_tlc=True,
            full_tlc_timeout=_FULL_TLC_TIMEOUT,
        )
        reward = max(floor, component)
    except Exception:
        reward = floor
    if any(issue in critical_issues for issue in issues):
        reward = min(reward, 0.14)
    if any(issue.startswith("forward_reference_") for issue in issues):
        reward = min(reward, 0.10)
    if module_cap is not None:
        reward = min(reward, module_cap)
    return reward


def fullspec_component_reward(
    prompts: list[Any] | None = None,
    completions: list[Any] | None = None,
    **_: Any,
) -> list[float]:
    """TRL GRPO reward function. One float per completion.

    Unlike per_action_tlc_reward, this function does NOT require harness
    columns — it evaluates complete specs end-to-end. The GRPOTrainer
    dataset only needs a `prompt` column.
    """
    completions = completions or []
    if not completions:
        return []

    texts = [_completion_text(c) for c in completions]
    targets = [_target_module_from_prompt(p) for p in (prompts or [])]
    if len(targets) != len(texts):
        targets = [None] * len(texts)
    n = len(texts)
    rewards: list[float] = [0.0] * n

    with ThreadPoolExecutor(max_workers=_REWARD_WORKERS) as pool:
        futures = {
            pool.submit(_grade_one, texts[i], targets[i]): i
            for i in range(n)
        }
        for fut in futures:
            i = futures[fut]
            try:
                rewards[i] = fut.result(timeout=_FULL_TLC_TIMEOUT + 30)
            except Exception:
                rewards[i] = 0.0

    _maybe_log_samples(texts, rewards, targets)
    return rewards


def _maybe_log_samples(texts: list[str], rewards: list[float], targets: list[str | None]) -> None:
    log_path = os.environ.get("CHATTLA_SAMPLE_LOG_PATH")
    if not log_path:
        return
    every = max(1, int(os.environ.get("CHATTLA_SAMPLE_LOG_EVERY", "1")))
    limit = max(1, int(os.environ.get("CHATTLA_SAMPLE_LOG_LIMIT", "8")))
    global _SAMPLE_LOG_CALL
    with _SAMPLE_LOG_LOCK:
        _SAMPLE_LOG_CALL += 1
        call_id = _SAMPLE_LOG_CALL
    if call_id % every != 0:
        return

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for i, text in enumerate(texts[:limit]):
            row = {
                "reward_call": call_id,
                "sample_index": i,
                "reward": rewards[i] if i < len(rewards) else None,
                "structural_floor": _structural_floor(text),
                "target_module": targets[i] if i < len(targets) else None,
                "produced_module": _module_name(text),
                "module_match": (
                    targets[i] == _module_name(text)
                    if i < len(targets) and targets[i]
                    else None
                ),
                "raw_chars": len(text),
                "starts_module": text.lstrip().startswith("---- MODULE"),
                "has_terminator": "====" in text,
                "syntax_issues": _syntax_hygiene_issues(text),
                "raw_completion": text,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
