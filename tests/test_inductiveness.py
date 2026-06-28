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


def test_enumerable_type_bound_expr_uses_length_relation_to_bound_sibling_sequences() -> None:
    module_src = r"""---- MODULE QueuedLike ----
EXTENDS Naturals, Sequences
CONSTANTS MaxQueue
VARIABLES enq, queue, committed
vars == << enq, queue, committed >>
Init == /\ enq = << >>
        /\ queue = << >>
        /\ committed = << >>
Next == /\ enq' = enq
        /\ queue' = queue
        /\ committed' = committed
Spec == Init /\ [][Next]_vars
TypeOK == /\ enq \in Seq(1..MaxQueue)
          /\ queue \in Seq(1..MaxQueue)
          /\ committed \in Seq(1..MaxQueue)
          /\ Len(enq) <= MaxQueue
          /\ Len(committed) + Len(queue) = Len(enq)
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ queue \in (UNION { [1..n -> (1..MaxQueue)] : n \in 0..MaxQueue })" in expr
    assert r"/\ committed \in (UNION { [1..n -> (1..MaxQueue)] : n \in 0..MaxQueue })" in expr


def test_enumerable_type_bound_expr_bounds_strictly_increasing_finite_domain_sequence() -> None:
    module_src = r"""---- MODULE IncreasingSeq ----
EXTENDS Naturals, Sequences
CONSTANTS MaxIssue
VARIABLE mem
vars == << mem >>
Init == mem = << >>
Next == /\ mem' = mem
Spec == Init /\ [][Next]_vars
MemInOrder == \A i \in 1..(Len(mem) - 1) : mem[i] < mem[i+1]
TypeOK == /\ mem \in Seq(1..MaxIssue)
          /\ MemInOrder
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ mem \in (UNION { [1..n -> (1..MaxIssue)] : n \in 0..MaxIssue })" in expr


def test_enumerable_type_bound_expr_expands_typeok_alias_to_helper_invariant() -> None:
    module_src = r"""---- MODULE AliasTypeOK ----
EXTENDS Naturals
CONSTANT C
VARIABLES active, rejected
vars == << active, rejected >>
Init == /\ active = 0
        /\ rejected = 0
Next == /\ active' = active
        /\ rejected' = rejected
Spec == Init /\ [][Next]_vars
CapacityInv == active \in 0..C /\ rejected \in 0..C
TypeOK == CapacityInv
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ active \in 0..C" in expr
    assert r"/\ rejected \in 0..C" in expr


def test_enumerable_type_bound_expr_orders_direct_domains_before_relational_clauses() -> None:
    module_src = r"""---- MODULE OrderedInit ----
EXTENDS Naturals
CONSTANT K
VARIABLES credits, inflight
vars == << credits, inflight >>
Init == /\ credits = K
        /\ inflight = 0
Next == /\ credits' = credits
        /\ inflight' = inflight
Spec == Init /\ [][Next]_vars
CreditInv == credits + inflight = K /\ inflight \in 0..K
TypeOK == credits \in 0..K /\ CreditInv
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    lines = [line.strip() for line in expr.splitlines() if line.strip()]
    assert lines[:2] == [r"/\ credits \in 0..K", r"/\ inflight \in 0..K"]
    assert lines[2] == r"/\ credits + inflight = K"
