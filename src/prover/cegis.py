"""CEGIS orchestrator for v2 safety proofs.

Counterexample-guided inductive-invariant search: propose a candidate, ask the
TLC oracle (`inductiveness.check_inductive`) whether it is inductive, and if not
feed the counterexample-to-induction (CTI) back to the proposer to strengthen
it. The proposer is injected (a stub in tests; the Ollama teacher in production),
so the loop itself is fully offline-testable.

On success, ties into the deterministic skeleton codegen so the discovered
invariant becomes a concrete TLAPS proof outline. Leaf discharge (running tlapm)
is a separate, remote step.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from src.prover.inductiveness import check_inductive
from src.prover.obligation_router import classify_obligation
from src.prover.skeleton import SafetySkeletonSpec, safety_proof_skeleton

# A proposer takes (module_src, current_candidate_expr, cti) and returns a new
# TLA+ predicate to conjoin, or None to give up.
InvariantProposer = Callable[[str, str, str], Optional[str]]

_CANDIDATE_OP = "ChatTLA_Candidate"
_END_RE = re.compile(r"^={4,}\s*$", re.M)
_BOX_RE = re.compile(r"\[\]\s*\(?\s*([A-Za-z_]\w*)")


@dataclass
class Attempt:
    candidate: str
    inductive: bool
    cti: Optional[str]


@dataclass
class CEGISResult:
    status: str  # "inductive" | "exhausted" | "error"
    invariant: Optional[str] = None
    attempts: list[Attempt] = field(default_factory=list)


def _conjoin(conjuncts: list[str]) -> str:
    return " /\\ ".join(f"({c})" for c in conjuncts)


def _inject_candidate(module_src: str, conjuncts: list[str]) -> str:
    line = f"{_CANDIDATE_OP} == {_conjoin(conjuncts)}\n"
    m = _END_RE.search(module_src)
    if m:
        return module_src[: m.start()] + line + module_src[m.start():]
    return module_src.rstrip() + "\n" + line + ("=" * 20) + "\n"


def search_inductive_invariant(
    module_src: str,
    base_predicate: str,
    proposer: InvariantProposer,
    max_iters: int = 10,
) -> CEGISResult:
    """Search for an inductive strengthening of ``base_predicate``.

    Each iteration injects ``ChatTLA_Candidate == c1 /\\ c2 /\\ ...`` into the
    module and asks TLC whether it is inductive (TypeOK supplies enumerability
    downstream). A non-inductive result yields a CTI handed to ``proposer`` for
    the next strengthening conjunct.
    """
    conjuncts = [base_predicate]
    attempts: list[Attempt] = []
    seen: set[str] = set()

    for _ in range(max_iters):
        cand_expr = _conjoin(conjuncts)
        if cand_expr in seen:
            return CEGISResult("exhausted", None, attempts)
        seen.add(cand_expr)

        res = check_inductive(_inject_candidate(module_src, conjuncts), _CANDIDATE_OP)
        if res.error:
            attempts.append(Attempt(cand_expr, False, None))
            return CEGISResult("error", None, attempts)

        attempts.append(Attempt(cand_expr, res.inductive, res.cti))
        if res.inductive:
            return CEGISResult("inductive", cand_expr, attempts)

        new_conjunct = proposer(module_src, cand_expr, res.cti or "")
        if not new_conjunct or new_conjunct in conjuncts:
            return CEGISResult("exhausted", None, attempts)
        conjuncts.append(new_conjunct)

    return CEGISResult("exhausted", None, attempts)


def prove_safety(
    module_src: str,
    theorem_text: str,
    proposer: InvariantProposer,
    base_predicate: Optional[str] = None,
    next_action_names: Optional[list[str]] = None,
    max_iters: int = 10,
) -> dict:
    """Route a theorem, run CEGIS for safety, and emit a proof skeleton.

    Returns a dict with at least ``status``. ``status="unsupported"`` for
    non-safety goals (e.g. liveness) — those need a different strategy.
    """
    kind = classify_obligation(theorem_text)
    if kind not in ("safety_invariance", "type_correctness"):
        return {"status": "unsupported", "kind": kind}

    box = _BOX_RE.search(theorem_text)
    property_name = box.group(1) if box else None
    base = base_predicate or property_name
    if not base:
        return {"status": "no_invariant", "kind": kind}

    res = search_inductive_invariant(module_src, base, proposer, max_iters)
    out: dict = {
        "status": res.status,
        "kind": kind,
        "invariant": res.invariant,
        "attempts": len(res.attempts),
    }
    if res.status == "inductive" and next_action_names:
        out["skeleton"] = safety_proof_skeleton(
            SafetySkeletonSpec(
                invariant_name="Inv",
                next_action_names=next_action_names,
                property_name=property_name,
            )
        )
    return out
