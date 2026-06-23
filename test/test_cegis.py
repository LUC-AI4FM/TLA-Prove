"""Tests for the CEGIS orchestrator — the loop that ties the v2 pillars together:
propose invariant -> TLC inductiveness check -> counterexample -> strengthen.

Uses a real (tiny, finite) TLA+ module so the inductiveness oracle runs actual
TLC. The LLM proposer is injected, so here it is a scripted stub.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.prover.cegis import search_inductive_invariant, prove_safety

# Two synchronized mod-4 counters. `x = y` is inductive; `x <= y` is NOT
# (from x=0,y=3 a step yields x=1,y=0), but `x <= y /\ x = y` is.
TWO_COUNTER = """\
---- MODULE TwoCounter ----
EXTENDS Naturals
VARIABLES x, y
TypeOK == x \\in 0..3 /\\ y \\in 0..3
Init == x = 0 /\\ y = 0
Next == x' = (x + 1) % 4 /\\ y' = (y + 1) % 4
vars == <<x, y>>
============================
"""


def _scripted_proposer(queue):
    q = list(queue)

    def propose(module_src, candidate, cti):
        return q.pop(0) if q else None

    return propose


def test_already_inductive_returns_immediately():
    res = search_inductive_invariant(TWO_COUNTER, "x = y", _scripted_proposer([]), max_iters=5)
    assert res.status == "inductive"
    assert len(res.attempts) == 1


def test_strengthening_reaches_inductive():
    res = search_inductive_invariant(
        TWO_COUNTER, "x <= y", _scripted_proposer(["x = y"]), max_iters=5
    )
    assert res.status == "inductive"
    assert len(res.attempts) == 2
    assert "x = y" in res.invariant and "x <= y" in res.invariant


def test_exhausted_when_proposer_gives_up():
    res = search_inductive_invariant(
        TWO_COUNTER, "x <= y", _scripted_proposer([]), max_iters=5
    )
    assert res.status == "exhausted"


def test_prove_safety_routes_away_from_liveness():
    out = prove_safety(TWO_COUNTER, "THEOREM Spec => <>Done", _scripted_proposer([]))
    assert out["status"] == "unsupported"


def test_prove_safety_finds_invariant_and_emits_skeleton():
    out = prove_safety(
        TWO_COUNTER,
        "THEOREM Spec => []Safe",
        _scripted_proposer([]),
        base_predicate="x = y",
        next_action_names=["Next"],
    )
    assert out["status"] == "inductive"
    assert out["invariant"] is not None
    assert "QED" in out["skeleton"]
