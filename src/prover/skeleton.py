"""Deterministic codegen of a standard hierarchical TLAPS *safety* proof.

Almost every TLA+ safety proof has a fixed shape: show the invariant holds in
the initial state, prove it is inductive (one ``CASE`` per ``Next`` disjunct,
plus a stuttering ``UNCHANGED vars`` case), optionally derive a target property
from the invariant, and discharge the temporal ``Spec`` goal with ``PTL``.

This module emits that skeleton as a string — no LLM, fully deterministic — so
the proof-search system has a known-good scaffold to start from (or fall back
to) before invoking heavier machinery.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SafetySkeletonSpec:
    invariant_name: str               # e.g. "Inv"
    next_action_names: list[str]      # Next disjuncts, e.g. ["Request(p)", "Enter(p)"]
    property_name: str | None = None  # optional Inv => Property step, e.g. "MutualExclusion"
    vars_name: str = "vars"
    include_unchanged_case: bool = True


_INDENT = "  "


def _bare_name(action: str) -> str:
    """Strip an action's parameter list, e.g. ``Request(p)`` -> ``Request``."""
    head, _, _ = action.partition("(")
    return head.strip()


def safety_proof_skeleton(spec: SafetySkeletonSpec) -> str:
    """Emit a standard hierarchical TLAPS safety-proof skeleton for ``spec``."""
    inv = spec.invariant_name
    out: list[str] = []

    # <1>1. Init => Inv
    out.append(f"<1>1. Init => {inv}")
    out.append(f"{_INDENT}BY DEF Init, {inv}")

    # <1>2. Inv /\ [Next]_vars => Inv'  (the inductive step)
    out.append(f"<1>2. {inv} /\\ [Next]_{spec.vars_name} => {inv}'")

    sub_labels: list[str] = []
    idx = 0
    for action in spec.next_action_names:
        idx += 1
        label = f"<2>{idx}"
        sub_labels.append(label)
        out.append(f"{_INDENT}{label}. CASE {action}")
        out.append(f"{_INDENT * 2}BY DEF {inv}, {_bare_name(action)}")

    if spec.include_unchanged_case:
        idx += 1
        label = f"<2>{idx}"
        sub_labels.append(label)
        out.append(f"{_INDENT}{label}. CASE UNCHANGED {spec.vars_name}")
        out.append(f"{_INDENT * 2}BY DEF {inv}, {spec.vars_name}")

    out.append(f"{_INDENT}<2> QED")
    out.append(f"{_INDENT * 2}BY {', '.join(sub_labels)} DEF Next")

    # <1>3. Inv => Property  (optional)
    outer_labels = ["<1>1", "<1>2"]
    if spec.property_name is not None:
        out.append(f"<1>3. {inv} => {spec.property_name}")
        out.append(f"{_INDENT}BY DEF {inv}, {spec.property_name}")
        outer_labels.append("<1>3")

    # <1> QED
    out.append("<1> QED")
    out.append(f"{_INDENT}BY {', '.join(outer_labels)}, PTL DEF Spec")

    return "\n".join(out)
