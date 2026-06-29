"""Stop policy and metrics for long Ralph verifier-repair loops.

The production loop behaves like tla-generator/Ralph: keep repairing until the
candidate passes the verifier stack. Fixed pass@K cutoffs remain evaluation
metrics, not stopping criteria.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class LongRunStep:
    iteration: int
    score: float
    phase: str
    failure_signature: str
    spec_hash: str
    success: bool = False
    malformed: bool = False


@dataclass(frozen=True)
class StopDecision:
    stop: bool
    reason: str = ""


def stable_spec_hash(spec: str) -> str:
    """Hash normalized-enough spec text for repeated-output detection."""
    collapsed = "\n".join(line.rstrip() for line in (spec or "").strip().splitlines())
    return sha1(collapsed.encode("utf-8", "replace")).hexdigest()[:16]


def failure_signature(phase: str, output: str, cap: int = 500) -> str:
    """Coarse fingerprint that ignores digits and volatile whitespace."""
    text = "".join(ch for ch in (output or "")[:cap] if not ch.isdigit())
    text = " ".join(text.split())
    return f"{phase}|{text[:cap]}"


def should_stop(
    steps: Sequence[LongRunStep],
    *,
    max_iters: int = 0,
    repeated_signature_limit: int = 4,
    repeated_spec_limit: int = 3,
    no_improvement_limit: int = 8,
    malformed_limit: int = 3,
    min_delta: float = 0.01,
) -> StopDecision:
    """Return whether an adaptive Ralph loop should stop.

    ``max_iters`` is an optional watchdog. Set it to 0 or less to run without
    an iteration cap. Adequacy/TLC/SANY failures are repair signals, not stop
    conditions; the non-success stop is only repeated malformed output.
    """
    del repeated_signature_limit, repeated_spec_limit, no_improvement_limit, min_delta

    if not steps:
        return StopDecision(False)

    last = steps[-1]
    if last.success:
        return StopDecision(True, "success")

    if max_iters > 0 and last.iteration >= max_iters:
        return StopDecision(True, "max_iters")

    tail_malformed = _tail_count(steps, lambda s: s.malformed)
    if tail_malformed >= malformed_limit:
        return StopDecision(True, "malformed_output")

    return StopDecision(False)


def pass_curve(
    rows: Iterable[Mapping[str, object]],
    cutoffs: Sequence[int] = (1, 3, 8, 15, 20),
) -> dict[str, float]:
    """Compute pass@K from trajectory summary rows."""
    materialized = list(rows)
    denom = len(materialized)
    if denom == 0:
        return {f"pass@{k}": 0.0 for k in cutoffs}

    out: dict[str, float] = {}
    for k in cutoffs:
        wins = 0
        for row in materialized:
            success = bool(row.get("success"))
            iterations = int(row.get("iterations") or 0)
            if success and iterations <= k:
                wins += 1
        out[f"pass@{k}"] = wins / denom
    return out


def _tail_count(steps: Sequence[LongRunStep], pred) -> int:
    count = 0
    for step in reversed(steps):
        if not pred(step):
            break
        count += 1
    return count


def _tail_equal_count(steps: Sequence[LongRunStep], getter, *, ignore_empty: bool) -> int:
    if not steps:
        return 0
    value = getter(steps[-1])
    if ignore_empty and not value:
        return 0
    count = 0
    for step in reversed(steps):
        if getter(step) != value:
            break
        count += 1
    return count
