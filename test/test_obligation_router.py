"""Tests for the structural obligation router.

Pins the priority ordering of the classifier and the tuple-delimiter trap:
``<<...>>`` are TLA+ tuple brackets, NOT eventually diamonds, so an
``UNCHANGED <<x, y>>`` clause must never be mistaken for a liveness goal.
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.prover.obligation_router import classify_obligation


def test_box_typeok_is_type_correctness():
    assert classify_obligation("THEOREM Spec => []TypeOK") == "type_correctness"


def test_box_named_invariant_is_safety():
    assert classify_obligation("THEOREM Spec => []MutualExclusion") == "safety_invariance"


def test_box_inv_is_safety():
    assert classify_obligation("THEOREM Spec => []Inv") == "safety_invariance"


def test_eventually_is_liveness():
    assert classify_obligation("THEOREM LiveSpec => <>Success") == "liveness_temporal"


def test_weak_fairness_outranks_typeok():
    # Has WF_, so liveness wins even though []TypeOK is present.
    assert classify_obligation("THEOREM Spec => []TypeOK /\\ WF_vars(Next)") == "liveness_temporal"


def test_leadsto_is_liveness():
    assert classify_obligation("THEOREM Spec => (Req ~> Resp)") == "liveness_temporal"


def test_box_state_predicate_is_safety():
    text = 'THEOREM Spec => [](\\A i \\in P : ~(pc[i]="cs"))'
    assert classify_obligation(text) == "safety_invariance"


def test_instance_qualified_spec_is_refinement():
    assert classify_obligation("THEOREM Spec => Impl!Spec") == "refinement"


def test_unchanged_tuple_is_not_liveness():
    # The `<<x, y>>` tuple must NOT trigger the `<>` diamond rule.
    text = "THEOREM Spec => [](UNCHANGED <<x, y>> => Inv)"
    assert classify_obligation(text) == "safety_invariance"


def test_enabledness_lemma_is_other():
    text = "LEMMA L == ASSUME TypeOK PROVE (ENABLED <<A>>_vars) <=> Q"
    assert classify_obligation(text) == "other"
