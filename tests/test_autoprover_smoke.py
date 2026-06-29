from pathlib import Path

import scripts.autoprover_smoke as smoke


MINI_MODULE = """---- MODULE Mini ----
EXTENDS Naturals
VARIABLE x
vars == <<x>>
Init == x = 0
Next == x' = x + 1
Spec == Init /\\ [][Next]_vars
TypeOK == x \\in 0..3
====
"""


def test_injected_typeok_theorem_extends_tlaps() -> None:
    proof_module = smoke._inject_typeok_theorem(MINI_MODULE, "OBVIOUS")

    assert "EXTENDS Naturals, TLAPS" in proof_module
    assert "THEOREM ChatTLA_TypeOKSafety == Spec => []TypeOK" in proof_module


def test_discover_accepts_explicit_module_list(tmp_path: Path) -> None:
    first = tmp_path / "First.tla"
    second = tmp_path / "Second.tla"
    first.write_text("---- MODULE First ----\n====\n", encoding="utf-8")
    second.write_text("---- MODULE Second ----\n====\n", encoding="utf-8")
    module_list = tmp_path / "modules.txt"
    module_list.write_text(
        f"\n# comment\n{first}\n{second}\n{first}\n",
        encoding="utf-8",
    )

    paths = smoke._discover_from_module_lists([module_list], limit=0)

    assert paths == [first.resolve(), second.resolve()]


def test_discover_module_list_treats_repo_relative_paths_as_repo_relative(tmp_path: Path) -> None:
    module_list = tmp_path / "modules.txt"
    module_list.write_text("scripts/autoprover_smoke.py\n", encoding="utf-8")

    paths = smoke._discover_from_module_lists([module_list], limit=0)

    assert paths == [(smoke.REPO / "scripts" / "autoprover_smoke.py").resolve()]


def test_default_globs_include_materialized_tla_fallback() -> None:
    globs = smoke._default_globs()

    assert str(smoke.REPO / "outputs" / "materialized_tla" / "tla_descriptions" / "*.tla") in globs


def test_run_one_validates_temp_file_with_matching_module_name(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "Mini.tla"
    module_path.write_text(MINI_MODULE, encoding="utf-8")

    class Inductive:
        inductive = True
        error = None
        cti = None

    class Tlaps:
        tier = "proved"
        obligations_total = 1
        obligations_proved = 1
        obligations_failed = 0
        timed_out = False
        errors = []
        raw_output = "[INFO]: All 1 obligation proved."

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module Mini"

    seen: dict[str, str] = {}

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")
    monkeypatch.setattr(smoke, "_tlapm_path", lambda: "/bin/true")

    def fake_validate_string(content: str, *, module_name: str, **_kwargs) -> Tlaps:
        seen["module_name"] = module_name
        seen["header"] = content.splitlines()[0]
        return Tlaps()

    monkeypatch.setattr(smoke, "validate_tlaps_string", fake_validate_string)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=True)

    assert row["status"] == "tlaps_proved"
    assert seen == {"module_name": "Mini", "header": "---- MODULE Mini ----"}


def test_run_one_skips_known_tlaps_tuple_binder_parse_incompatibility(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "TupleBinder.tla"
    module_path.write_text(
        """---- MODULE TupleBinder ----
EXTENDS Naturals
VARIABLE grid
vars == grid
TypeOK == grid \\in [1..3 -> BOOLEAN]
sc[<<x, y>> \\in (0 .. 3) \\X (0 .. 3)] == 0
Init == grid \\in [1..3 -> BOOLEAN]
Next == grid' = grid
Spec == Init /\\ [][Next]_vars
====
""",
        encoding="utf-8",
    )

    class Inductive:
        inductive = True
        error = None
        cti = None

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module TupleBinder"

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "_tlapm_path", lambda: "/bin/true")

    called = {"validate": False}

    def fail_validate(*_args, **_kwargs):
        called["validate"] = True
        raise AssertionError("validate_string should not be called for known parser-incompatible syntax")

    monkeypatch.setattr(smoke, "validate_tlaps_string", fail_validate)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=True)

    assert row["status"] == "skipped"
    assert row["reason"] == "tlaps_tuple_binder_parse_incompatible"
    assert called["validate"] is False


def test_run_one_skips_sany_invalid_candidate_before_tlc(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "BrokenSyntax.tla"
    module_path.write_text(
        """---- MODULE BrokenSyntax ----
EXTENDS Naturals
VARIABLE x
vars == <<x>>
Init == x = 0
Next == x' = x + 1
Spec == Init /\\ [][Next]_vars
TypeOK == x \\in
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = False
        errors = ["*** Errors: parse failure"]
        raw_output = "*** Errors: parse failure"

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult(), raising=False)

    def fail_check_inductive(*_args, **_kwargs):
        raise AssertionError("check_inductive should not run after SANY rejection")

    monkeypatch.setattr(smoke, "check_inductive", fail_check_inductive)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skipped"
    assert row["reason"] == "sany_parse_or_semantic_invalid"
    assert row["sany_errors"] == ["*** Errors: parse failure"]


def test_run_one_accepts_seq_based_typeok_with_finite_len_guard(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "SeqBounded.tla"
    module_path.write_text(
        r"""---- MODULE SeqBounded ----
EXTENDS Naturals, Sequences
CONSTANTS MaxQueue
VARIABLES q
vars == <<q>>
Init == q = <<>>
Next == /\ Len(q) < MaxQueue
        /\ q' = Append(q, Len(q) + 1)
Spec == Init /\ [][Next]_vars
TypeOK == /\ q \in Seq(1..MaxQueue)
          /\ Len(q) <= MaxQueue
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module SeqBounded"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_append_sequence_domain_inferred_from_length_and_updates(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "MissingDomain.tla"
    module_path.write_text(
        r"""---- MODULE MissingDomain ----
EXTENDS Naturals, Sequences
VARIABLES seq, broadcast, delivered
vars == << seq, broadcast, delivered >>
Init == /\ seq = 0
        /\ broadcast = << >>
        /\ delivered = 0
Next == /\ seq < 3
        /\ seq' = seq + 1
        /\ broadcast' = Append(broadcast, seq + 1)
        /\ delivered' = delivered
Spec == Init /\ [][Next]_vars
TypeOK == /\ seq \in 0..3
          /\ Len(broadcast) = seq
          /\ \A i \in 1..Len(broadcast) : broadcast[i] = i
          /\ delivered \in 0..3
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module MissingDomain"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_finite_subseteq_variable_domains(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "FiniteSubset.tla"
    module_path.write_text(
        r"""---- MODULE FiniteSubset ----
EXTENDS Naturals, FiniteSets
Vals == 0..2
VARIABLES idx, inflight, acks
vars == << idx, inflight, acks >>
Init == /\ idx = 0
        /\ inflight = {}
        /\ acks = {}
Next == /\ idx < 2
        /\ idx' = idx + 1
        /\ inflight' = inflight \cup {idx}
        /\ acks' = acks
Spec == Init /\ [][Next]_vars
TypeOK == /\ idx \in 0..2
          /\ inflight \subseteq Vals
          /\ acks \subseteq {0, 1}
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module FiniteSubset"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_subset_constructor_in_direct_variable_domain(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "SubsetRange.tla"
    module_path.write_text(
        r"""---- MODULE SubsetRange ----
EXTENDS Naturals, FiniteSets
Nodes == 1..3
Vals == {"v0", "v1"}
VARIABLES sigs, round
vars == << sigs, round >>
Init == /\ sigs = [v \in Vals |-> {}]
        /\ round = 0
Next == /\ round < 2
        /\ sigs' = [sigs EXCEPT !["v0"] = @ \cup {1}]
        /\ round' = round + 1
Spec == Init /\ [][Next]_vars
TypeOK == /\ sigs \in [Vals -> SUBSET Nodes]
          /\ round \in 0..2
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module SubsetRange"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_helper_conjunct_when_variables_have_direct_domains(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "HelperConjunct.tla"
    module_path.write_text(
        r"""---- MODULE HelperConjunct ----
EXTENDS Naturals, FiniteSets
Procs == {"p1", "p2"}
NoHolder == "none"
VARIABLES holder, waiters
vars == << holder, waiters >>
Init == /\ holder = NoHolder
        /\ waiters = {}
Next == /\ holder = NoHolder
        /\ holder' = "p1"
        /\ waiters' = waiters
Spec == Init /\ [][Next]_vars
MutexSafe == /\ (holder = NoHolder) \/ (holder \in Procs)
             /\ holder \notin waiters
TypeOK == /\ holder \in (Procs \cup {NoHolder})
          /\ waiters \subseteq Procs
          /\ MutexSafe
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module HelperConjunct"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_seq_domain_when_helper_conjunct_carries_len_bound(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "HelperBoundedSeq.tla"
    module_path.write_text(
        r"""---- MODULE HelperBoundedSeq ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module HelperBoundedSeq"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_seq_domain_when_helper_body_starts_without_conjunct_prefix(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "InlineHelperBoundedSeq.tla"
    module_path.write_text(
        r"""---- MODULE InlineHelperBoundedSeq ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module InlineHelperBoundedSeq"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_seq_domain_when_length_relation_bounds_sibling_sequences(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "QueuedLike.tla"
    module_path.write_text(
        r"""---- MODULE QueuedLike ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module QueuedLike"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_strictly_increasing_finite_domain_sequence(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "IncreasingSeq.tla"
    module_path.write_text(
        r"""---- MODULE IncreasingSeq ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module IncreasingSeq"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_typeok_alias_to_helper_invariant(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "AliasTypeOK.tla"
    module_path.write_text(
        r"""---- MODULE AliasTypeOK ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module AliasTypeOK"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_pointwise_function_domain_invariant(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "PointwiseFunction.tla"
    module_path.write_text(
        r"""---- MODULE PointwiseFunction ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module PointwiseFunction"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_multi_conjunct_pointwise_function_domain(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "PointwiseFunctionConjuncts.tla"
    module_path.write_text(
        r"""---- MODULE PointwiseFunctionConjuncts ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module PointwiseFunctionConjuncts"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_multiline_typeok_after_leading_quantified_clause(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "QuantifiedThenPlain.tla"
    module_path.write_text(
        r"""---- MODULE QuantifiedThenPlain ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module QuantifiedThenPlain"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_message_set_domain_inferred_from_updates(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "MessageUniverse.tla"
    module_path.write_text(
        r"""---- MODULE MessageUniverse ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module MessageUniverse"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_append_only_sequence_domain_inferred_from_updates(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "AppendOnlySeq.tla"
    module_path.write_text(
        r"""---- MODULE AppendOnlySeq ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module AppendOnlySeq"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_accepts_nested_function_domain_inferred_from_pointwise_bounds(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "NestedPointwise.tla"
    module_path.write_text(
        r"""---- MODULE NestedPointwise ----
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
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module NestedPointwise"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_retries_small_timeout_case_with_larger_budget(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "RetryTimeout.tla"
    module_path.write_text(
        r"""---- MODULE RetryTimeout ----
EXTENDS Naturals
VARIABLES msgs, chosen
vars == << msgs, chosen >>
Init == /\ msgs = {}
        /\ chosen = 0
Next == /\ msgs' = msgs
        /\ chosen' = chosen
Spec == Init /\ [][Next]_vars
TypeOK == /\ msgs \subseteq {0}
          /\ chosen \in 0..1
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module RetryTimeout"

    class Timeout:
        inductive = False
        error = "TLC timed out after 20s (INIT-as-predicate state space too large to enumerate)."
        cti = None

    class Success:
        inductive = True
        error = None
        cti = None

    calls: list[int] = []

    def fake_check_inductive(_src: str, _inv: str, *, timeout: int):
        calls.append(timeout)
        return Timeout() if len(calls) == 1 else Success()

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", fake_check_inductive)
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=20, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"
    assert calls == [20, 120]


def test_run_one_does_not_retry_large_timeout_case(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "NoRetryTimeout.tla"
    module_path.write_text(
        r"""---- MODULE NoRetryTimeout ----
EXTENDS Naturals
VARIABLES a, b, c
vars == << a, b, c >>
Init == /\ a = 0
        /\ b = 0
        /\ c = 0
Next == /\ a' = a
        /\ b' = b
        /\ c' = c
Spec == Init /\ [][Next]_vars
TypeOK == /\ a \in 0..1
          /\ b \in 0..1
          /\ c \in 0..1
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module NoRetryTimeout"

    class Timeout:
        inductive = False
        error = "TLC timed out after 20s (INIT-as-predicate state space too large to enumerate)."
        cti = None

    calls: list[int] = []

    def fake_check_inductive(_src: str, _inv: str, *, timeout: int):
        calls.append(timeout)
        return Timeout()

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", fake_check_inductive)

    row = smoke.run_one(module_path, tlc_timeout=20, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "tlc_error"
    assert calls == [20]


def test_run_one_falls_back_to_post_spec_safety_invariant(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "FallbackInvariant.tla"
    module_path.write_text(
        r"""---- MODULE FallbackInvariant ----
EXTENDS Naturals
VARIABLES x
vars == <<x>>
Init == x = 0
Next == x' = x
Spec == Init /\ [][Next]_vars
SafetyInv == x \in 0..1
TypeOK == x \in 0..1
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module FallbackInvariant"

    class TypeOKFail:
        inductive = False
        error = "TLC timed out after 20s (INIT-as-predicate state space too large to enumerate)."
        cti = None

    class SafetyOk:
        inductive = True
        error = None
        cti = None

    calls: list[tuple[str, int]] = []

    def fake_check_inductive(_src: str, inv: str, *, timeout: int):
        calls.append((inv, timeout))
        return TypeOKFail() if inv == "TypeOK" else SafetyOk()

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", fake_check_inductive)
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=20, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"
    assert row["target"] == "Spec => []SafetyInv"
    assert row["invariant_name"] == "SafetyInv"
    assert calls == [("TypeOK", 20), ("SafetyInv", 20)]


def test_run_one_multiline_variables_block_still_checks_missing_direct_domain(
    monkeypatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "MultiVars.tla"
    module_path.write_text(
        r"""---- MODULE MultiVars ----
EXTENDS Naturals, Sequences, FiniteSets
Vals == 0..2
VARIABLES
    sBit,
    delivered,
    msgChan
vars == << sBit, delivered, msgChan >>
Init == /\ sBit = 0
        /\ delivered = << >>
        /\ msgChan = {}
Next == /\ sBit' = sBit
        /\ delivered' = delivered
        /\ msgChan' = msgChan
Spec == Init /\ [][Next]_vars
TypeOK == /\ sBit \in {0, 1}
          /\ msgChan \subseteq ({0,1} \X Vals)
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module MultiVars"

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())

    def fail_check_inductive(*_args, **_kwargs):
        raise AssertionError("check_inductive should not run when multiline VARIABLES still leave a direct domain missing")

    monkeypatch.setattr(smoke, "check_inductive", fail_check_inductive)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skipped"
    assert row["reason"] == "typeok_missing_variable_domain_delivered"


def test_run_one_skips_infinite_builtin_direct_domain(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "InfiniteNat.tla"
    module_path.write_text(
        r"""---- MODULE InfiniteNat ----
EXTENDS Naturals
VARIABLES head, tail
vars == << head, tail >>
Init == /\ head = 0
        /\ tail = 0
Next == /\ head' = head
        /\ tail' = tail
Spec == Init /\ [][Next]_vars
TypeOK == /\ head \in Nat
          /\ tail \in Nat
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module InfiniteNat"

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())

    def fail_check_inductive(*_args, **_kwargs):
        raise AssertionError("check_inductive should not run for obviously infinite Nat direct domains")

    monkeypatch.setattr(smoke, "check_inductive", fail_check_inductive)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skipped"
    assert row["reason"] == "typeok_infinite_builtin_domain_head"


def test_run_one_skips_function_domain_with_infinite_builtin_range(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "InfiniteFunctionRange.tla"
    module_path.write_text(
        r"""---- MODULE InfiniteFunctionRange ----
EXTENDS Naturals
Procs == {"p1", "p2"}
VARIABLES num, flag
vars == << num, flag >>
Init == /\ num = [i \in Procs |-> 0]
        /\ flag = [i \in Procs |-> FALSE]
Next == /\ num' = num
        /\ flag' = flag
Spec == Init /\ [][Next]_vars
TypeOK == /\ num \in [Procs -> Nat]
          /\ flag \in [Procs -> BOOLEAN]
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module InfiniteFunctionRange"

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())

    def fail_check_inductive(*_args, **_kwargs):
        raise AssertionError("check_inductive should not run for function ranges over infinite builtins")

    monkeypatch.setattr(smoke, "check_inductive", fail_check_inductive)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skipped"
    assert row["reason"] == "typeok_function_range_uses_infinite_builtin"


def test_run_one_skips_finite_but_astronomical_typeok_state_space(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "HugeFinite.tla"
    module_path.write_text(
        r"""---- MODULE HugeFinite ----
EXTENDS Naturals, FiniteSets
Procs == {0, 1}
MaxMsgs == 2
VARIABLES vc, channel, sentCount
vars == << vc, channel, sentCount >>
Init == /\ vc = [p \in Procs |-> [q \in Procs |-> 0]]
        /\ channel = {}
        /\ sentCount = [p \in Procs |-> 0]
Next == /\ vc' = vc
        /\ channel' = channel
        /\ sentCount' = sentCount
Spec == Init /\ [][Next]_vars
TypeOK == /\ vc \in [Procs -> [Procs -> 0..MaxMsgs]]
          /\ sentCount \in [Procs -> 0..MaxMsgs]
          /\ channel \subseteq (Procs \X [Procs -> 0..MaxMsgs])
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module HugeFinite"

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())

    def fail_check_inductive(*_args, **_kwargs):
        raise AssertionError("check_inductive should not run for obviously enormous but finite INIT state spaces")

    monkeypatch.setattr(smoke, "check_inductive", fail_check_inductive)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skipped"
    assert row["reason"] == "typeok_init_state_space_too_large"


def test_run_one_allows_moderate_finite_typeok_state_space(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "ModerateFinite.tla"
    module_path.write_text(
        r"""---- MODULE ModerateFinite ----
EXTENDS Naturals, FiniteSets
Nodes == {1, 2, 3}
Values == {1, 2, 3}
MaxRound == 2
VARIABLES known, alive, round, decision
vars == << known, alive, round, decision >>
Init == /\ known = [n \in Nodes |-> {n}]
        /\ alive = [n \in Nodes |-> TRUE]
        /\ round = 0
        /\ decision = [n \in Nodes |-> 0]
Next == /\ known' = known
        /\ alive' = alive
        /\ round' = round
        /\ decision' = decision
Spec == Init /\ [][Next]_vars
TypeOK == /\ known \in [Nodes -> SUBSET Values]
          /\ alive \in [Nodes -> BOOLEAN]
          /\ round \in 0..MaxRound
          /\ decision \in [Nodes -> 0..3]
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module ModerateFinite"

    class Inductive:
        inductive = True
        error = None
        cti = None

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())
    monkeypatch.setattr(smoke, "check_inductive", lambda *_args, **_kwargs: Inductive())
    monkeypatch.setattr(smoke, "safety_proof_skeleton", lambda _spec: "OBVIOUS")

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=False)

    assert row["status"] == "skeleton_emitted"


def test_run_one_skips_modules_requiring_structured_constant_cfg(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "FunctionConstant.tla"
    module_path.write_text(
        r"""---- MODULE FunctionConstant ----
EXTENDS Naturals
CONSTANT Node, Capacity
ASSUME Capacity \in [Node -> Nat]
VARIABLE x
vars == <<x>>
Init == x = 0
Next == UNCHANGED x
Spec == Init /\ [][Next]_vars
TypeOK == x \in 0..1
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module FunctionConstant"

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())

    def fail_check_inductive(*_args, **_kwargs):
        raise AssertionError("check_inductive should not run for structured-constant cfg cases")

    monkeypatch.setattr(smoke, "check_inductive", fail_check_inductive)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=True)

    assert row["status"] == "skipped"
    assert row["reason"] == "assume_requires_function_constant_cfg"


def test_run_one_skips_sequence_backed_array_domains(monkeypatch, tmp_path: Path) -> None:
    module_path = tmp_path / "ArrayBacked.tla"
    module_path.write_text(
        r"""---- MODULE ArrayBacked ----
EXTENDS Naturals
CONSTANTS BuffSz, SymbolOrArbitrary
VARIABLE file_content
vars == <<file_content>>
ArrayOfAnyLength(T) == [length : Nat, elems : Seq(T)]
Init == file_content = [length |-> 0, elems |-> <<>>]
Next == UNCHANGED file_content
Spec == Init /\ [][Next]_vars
TypeOK == file_content \in ArrayOfAnyLength(SymbolOrArbitrary)
====
""",
        encoding="utf-8",
    )

    class SanyResult:
        valid = True
        errors = []
        raw_output = "Semantic processing of module ArrayBacked"

    monkeypatch.setattr(smoke, "validate_sany_string", lambda *_args, **_kwargs: SanyResult())

    def fail_check_inductive(*_args, **_kwargs):
        raise AssertionError("check_inductive should not run for sequence-backed array domains")

    monkeypatch.setattr(smoke, "check_inductive", fail_check_inductive)

    row = smoke.run_one(module_path, tlc_timeout=1, tlapm_timeout=1, run_tlaps=True)

    assert row["status"] == "skipped"
    assert row["reason"] == "typeok_uses_sequence_backed_array_domain"


def test_progress_summary_counts_rows_modules_and_statuses() -> None:
    rows = [
        {"module": "A", "status": "skipped"},
        {"module": "B", "status": "tlaps_partial"},
        {"module": "C", "status": "tlc_error"},
        {"module": "B", "status": "tlaps_partial"},
    ]

    summary = smoke.progress_summary(rows, job_id="170004.sophia-pbs-01")

    assert summary["job_id"] == "170004.sophia-pbs-01"
    assert summary["rows_so_far"] == 4
    assert summary["modules_seen"] == 3
    assert summary["statuses"] == {
        "skipped": 1,
        "tlaps_partial": 2,
        "tlc_error": 1,
    }


def test_progress_summary_carries_last_and_next_module_paths() -> None:
    rows = [
        {"module": "A", "module_path": "/tmp/A.tla", "status": "skipped"},
        {"module": "B", "module_path": "/tmp/B.tla", "status": "tlaps_partial"},
    ]

    summary = smoke.progress_summary(
        rows,
        job_id="170004.sophia-pbs-01",
        discovered_paths=[Path("/tmp/A.tla"), Path("/tmp/B.tla"), Path("/tmp/C.tla")],
    )

    assert summary["last_completed_module_path"] == "/tmp/B.tla"
    assert summary["last_completed_status"] == "tlaps_partial"
    assert summary["next_module_path"] == "/tmp/C.tla"
