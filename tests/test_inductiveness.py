from src.prover import inductiveness


def test_enumerable_type_bound_expr_rewrites_bounded_seq_domains() -> None:
    module_src = r"""---- MODULE SeqBounded ----
EXTENDS Naturals, Sequences
CONSTANTS MaxQueue
VARIABLES q, count
vars == << q, count >>
Init == /\ q = << >>
        /\ count = 0
Next == /\ q' = q
        /\ count' = count
Spec == Init /\ [][Next]_vars
TypeOK == /\ q \in Seq(1..MaxQueue)
          /\ count \in 0..MaxQueue
          /\ Len(q) <= MaxQueue
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ q \in (UNION { [1..n -> (1..MaxQueue)] : n \in 0..MaxQueue })" in expr
    assert r"/\ count \in 0..MaxQueue" in expr


def test_enumerable_type_bound_expr_follows_helper_conjunct_for_seq_bound() -> None:
    module_src = r"""---- MODULE HelperBoundedSeq ----
EXTENDS Naturals, Sequences
CONSTANTS K, Vals
VARIABLE queue
vars == << queue >>
Init == queue = << >>
Next == /\ queue' = queue
Spec == Init /\ [][Next]_vars
Bounded == /\ Len(queue) \in 0..K
           /\ \A i \in 1..Len(queue) : queue[i] \in Vals
TypeOK == /\ queue \in Seq(Vals)
          /\ Bounded
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ queue \in (UNION { [1..n -> (Vals)] : n \in 0..K })" in expr


def test_enumerable_type_bound_expr_accepts_helper_body_without_leading_conjunct() -> None:
    module_src = r"""---- MODULE InlineHelperBoundedSeq ----
EXTENDS Naturals, Sequences
CONSTANTS K, Vals
VARIABLE resident
vars == << resident >>
Init == resident = << >>
Next == /\ resident' = resident
Spec == Init /\ [][Next]_vars
Bounded == Len(resident) \in 0..K
TypeOK == /\ resident \in Seq(Vals)
          /\ Bounded
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ resident \in (UNION { [1..n -> (Vals)] : n \in 0..K })" in expr
