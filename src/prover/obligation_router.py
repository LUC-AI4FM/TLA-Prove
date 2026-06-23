"""Structural router that buckets a TLA+ goal into a proof strategy.

Cheap, deterministic triage for the v2 proof-search loop: it inspects only the
surface syntax of a ``THEOREM``/``LEMMA`` obligation — no LLM, no SANY, no TLAPS
— and names the strategy bucket a downstream tactic generator should target.

The one genuine pitfall is the eventually diamond ``<>``: TLA+ overloads angle
brackets so that ``<<`` and ``>>`` are tuple delimiters (e.g. ``<<x, y>>`` or
``UNCHANGED <<a, b>>``). We strip every ``<<...>>`` tuple — and any stray
``<<``/``>>`` tokens — before scanning for a real ``<>`` so an action subscript
or tuple never masquerades as a liveness property.
"""
from __future__ import annotations

import re

# A balanced (or stray) tuple-delimiter run. Greedy-but-line-local: any text
# bracketed by `<<` ... `>>`, plus bare `<<`/`>>` tokens, gets blanked so the
# leftover cannot contain a spurious `<>`.
_TUPLE_RE = re.compile(r"<<.*?>>|<<|>>", re.DOTALL)
# Temporal / fairness operators that mark a liveness obligation.
_EVENTUALLY_RE = re.compile(r"<>")
_LEADSTO_RE = re.compile(r"~>")
_FAIRNESS_RE = re.compile(r"\b(?:WF|SF)_")
# `Spec => []TypeOK` — box applied to the canonical type invariant.
_BOX_TYPEOK_RE = re.compile(r"\[\]\s*TypeOK\b")
# An instance reference like `Impl!Spec` (RHS of a refinement), or the word.
_INSTANCE_RE = re.compile(r"\w+\s*!\s*\w+")
_REFINEMENT_WORD_RE = re.compile(r"\bRefinement\b", re.IGNORECASE)
# `Spec => []P` — box applied to some state predicate.
_BOX_RE = re.compile(r"\[\]")


def classify_obligation(theorem_text: str) -> str:
    """Return the proof-strategy bucket for ``theorem_text``.

    One of ``"type_correctness"``, ``"safety_invariance"``,
    ``"liveness_temporal"``, ``"refinement"``, or ``"other"``. Rules are applied
    in strict priority order (liveness, then type-correctness, then refinement,
    then safety, else other); the first match wins.
    """
    text = theorem_text or ""
    # Liveness is checked on a tuple-stripped copy so `<<...>>` cannot supply a
    # phantom `<>` diamond. Fairness/leads-to operators are unambiguous as-is.
    detuple = _TUPLE_RE.sub(" ", text)
    if (
        _EVENTUALLY_RE.search(detuple)
        or _LEADSTO_RE.search(text)
        or _FAIRNESS_RE.search(text)
    ):
        return "liveness_temporal"

    if _BOX_TYPEOK_RE.search(text):
        return "type_correctness"

    if _INSTANCE_RE.search(detuple) or _REFINEMENT_WORD_RE.search(text):
        return "refinement"

    if _BOX_RE.search(text):
        return "safety_invariance"

    return "other"
