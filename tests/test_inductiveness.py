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


def test_enumerable_type_bound_expr_rewrites_pointwise_function_domain_invariant() -> None:
    module_src = r"""---- MODULE PointwiseFunction ----
EXTENDS Naturals
CONSTANT N
ASSUME N \in 1..3
Tasks == 0..(N-1)
Q == 2
VARIABLES used, clock
vars == << used, clock >>
Init == /\ used = [t \in Tasks |-> 0]
        /\ clock = 0
Next == /\ used' = used
        /\ clock' = clock
QuotaInv == \A t \in Tasks : used[t] \in 0..Q
TypeOK == /\ clock \in 0..3
          /\ QuotaInv
Spec == Init /\ [][Next]_vars
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ used \in [Tasks -> 0..Q]" in expr
    assert r"/\ clock \in 0..3" in expr


def test_enumerable_type_bound_expr_rewrites_multiple_pointwise_domains_in_one_quantifier() -> None:
    module_src = r"""---- MODULE PointwiseFunctionConjuncts ----
EXTENDS Naturals
CONSTANT N
ASSUME N \in 1..3
Tasks == 0..(N-1)
Levels == 0..2
VARIABLES level, used, running
vars == << level, used, running >>
Init == /\ level = [t \in Tasks |-> 0]
        /\ used = [t \in Tasks |-> 0]
        /\ running = N
Next == /\ level' = level
        /\ used' = used
        /\ running' = running
LevelInv == \A t \in Tasks : level[t] \in Levels /\ used[t] \in 0..1
TypeOK == /\ running \in Tasks \cup {N}
          /\ LevelInv
Spec == Init /\ [][Next]_vars
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ level \in [Tasks -> Levels]" in expr
    assert r"/\ used \in [Tasks -> 0..1]" in expr


def test_enumerable_type_bound_expr_keeps_multiline_top_level_conjuncts_after_quantifier() -> None:
    module_src = r"""---- MODULE QuantifiedThenPlain ----
EXTENDS Naturals
CONSTANT N
ASSUME N \in 1..3
Tasks == 0..(N-1)
VARIABLES used, alarm
vars == << used, alarm >>
Init == /\ used = [t \in Tasks |-> 0]
        /\ alarm = FALSE
Next == /\ used' = used
        /\ alarm' = alarm
TypeOK == /\ \A t \in Tasks : used[t] \in 0..1
          /\ alarm \in BOOLEAN
Spec == Init /\ [][Next]_vars
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ used \in [Tasks -> 0..1]" in expr
    assert r"/\ alarm \in BOOLEAN" in expr


def test_enumerable_type_bound_expr_infers_message_set_domain_from_updates() -> None:
    module_src = r"""---- MODULE MessageUniverse ----
EXTENDS Naturals
Clients == {"c1", "c2"}
Addrs == {"a1", "a2"}
VARIABLES msgs, phase
vars == << msgs, phase >>
Init == /\ msgs = {}
        /\ phase = 0
Discover(c) == /\ phase = 0
               /\ msgs' = msgs \cup {<<"discover", c>>}
               /\ phase' = 1
Offer(c, a) == /\ phase = 1
               /\ msgs' = (msgs \ {<<"discover", c>>}) \cup {<<"offer", c, a>>}
               /\ phase' = 0
Next == \/ \E c \in Clients : Discover(c)
        \/ \E c \in Clients, a \in Addrs : Offer(c, a)
Spec == Init /\ [][Next]_vars
TypeOK == phase \in 0..1
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ phase \in 0..1" in expr
    assert r"/\ msgs \in (SUBSET" in expr
    assert r'<<"discover", c>>' in expr
    assert r'<<"offer", c, a>>' in expr


def test_enumerable_type_bound_expr_infers_append_only_sequence_domain_from_updates() -> None:
    module_src = r"""---- MODULE AppendOnlySeq ----
EXTENDS Naturals, Sequences
MaxMsgs == 3
VARIABLES seq, broadcast
vars == << seq, broadcast >>
Init == /\ seq = 0
        /\ broadcast = << >>
Assign == /\ seq < MaxMsgs
          /\ seq' = seq + 1
          /\ broadcast' = Append(broadcast, seq + 1)
Next == Assign
Spec == Init /\ [][Next]_vars
TypeOK == /\ seq \in 0..MaxMsgs
          /\ Len(broadcast) = seq
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ seq \in 0..MaxMsgs" in expr
    assert r"/\ broadcast \in (UNION { [1..n -> (1..(MaxMsgs + 1))] : n \in 0..MaxMsgs })" in expr


def test_enumerable_type_bound_expr_rewrites_nested_pointwise_function_domains() -> None:
    module_src = r"""---- MODULE NestedPointwise ----
EXTENDS Naturals
CONSTANT N
ASSUME N \in 2..3
Procs == 0..(N-1)
Res == {0, 1}
Total == [r \in Res |-> 2]
VARIABLES alloc, available
vars == << alloc, available >>
Init == /\ alloc = [p \in Procs |-> [r \in Res |-> 0]]
        /\ available = Total
Next == /\ alloc' = alloc
        /\ available' = available
Spec == Init /\ [][Next]_vars
TypeOK == /\ \A p \in Procs, r \in Res : alloc[p][r] \in 0..Total[r]
          /\ \A r \in Res : available[r] \in 0..Total[r]
====
"""

    expr = inductiveness._enumerable_type_bound_expr(module_src)

    assert expr is not None
    assert r"/\ alloc \in [Procs -> [Res -> 0..(2)]]" in expr
    assert r"/\ available \in [Res -> 0..(2)]" in expr
