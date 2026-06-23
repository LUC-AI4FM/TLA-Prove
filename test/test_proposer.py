"""Tests for the invariant proposer — the production CEGIS proposer that turns a
counterexample-to-induction into a strengthening conjunct via the teacher model.

The network call is injected (`chat_fn`), so prompt construction, response
parsing, and the end-to-end drive of the CEGIS loop are all tested offline with
zero Ollama spend. The live cloud call is a thin documented default, not tested.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.prover.proposer import build_strengthen_prompt, parse_invariant, make_invariant_proposer
from src.prover.cegis import search_inductive_invariant

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


def test_prompt_includes_module_candidate_and_cti():
    p = build_strengthen_prompt("---- MODULE M ----\n...", "(x <= y)", "State1 x=0,y=3 -> State2 x=1,y=0")
    assert "x <= y" in p
    assert "x=0,y=3" in p
    assert "MODULE M" in p


def test_parse_strips_fences_and_definition_lhs():
    assert parse_invariant("```tla\nInv2 == x = y\n```") == "x = y"


def test_parse_plain_predicate():
    assert parse_invariant("x = y") == "x = y"


def test_parse_rejects_refusal_and_empty():
    assert parse_invariant("I cannot determine a strengthening here.") is None
    assert parse_invariant("") is None


def test_proposer_drives_cegis_to_inductive():
    # Fake teacher returns the correct strengthening conjunct.
    chat_fn = lambda prompt: "Here you go:\n```\nx = y\n```"
    proposer = make_invariant_proposer(chat_fn)
    res = search_inductive_invariant(TWO_COUNTER, "x <= y", proposer, max_iters=5)
    assert res.status == "inductive"
    assert "x = y" in res.invariant
