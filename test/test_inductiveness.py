"""Tests for the TLC-based inductiveness checker (CEGIS oracle).

These exercise the core inductive-invariant check used by the v2 proof-search
loop: given a module and a candidate invariant name, decide whether
``Inv /\\ [Next]_vars => Inv'`` holds, returning a counterexample-to-induction
(CTI) when it does not.

TLC runs spawn a JVM and can take several seconds each, so these are slow by
unit-test standards but well within the 90s default timeout.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.prover.inductiveness import (  # noqa: E402
    InductivenessResult,
    _build_cfg,
    _inject_ind_init,
    _rewrite_enumerable_clause,
    check_inductive,
)


# A tiny bounded module: x cycles 0->1->2->3->0 via a mod-4 increment.
# Variables are pinned to a finite type so INIT-as-predicate enumeration works.
_BOUNDED_COUNTER = """\
---- MODULE BoundedCounter ----
EXTENDS Naturals
VARIABLE x
TypeOK == x \\in 0..3
Init == x = 0
Next == x' = (x + 1) % 4
vars == x
================================
"""

# Same module plus a candidate invariant that is true of reachable states but
# NOT inductive: from x=2, Next yields x=3, violating x < 3.
_BOUNDED_COUNTER_BAD = """\
---- MODULE BoundedCounter ----
EXTENDS Naturals
VARIABLE x
TypeOK == x \\in 0..3
Bad == x < 3
Init == x = 0
Next == x' = (x + 1) % 4
vars == x
================================
"""

# Garbage that SANY cannot parse.
_BROKEN = """\
---- MODULE Broken ----
this is not valid TLA+ @@@ ???
================================
"""

_HELPER_TYPEOK = """\
---- MODULE HelperTypeOK ----
EXTENDS Naturals, FiniteSets
Procs == {"p1", "p2"}
NoHolder == "none"
VARIABLES holder, waiters
vars == << holder, waiters >>
Init == /\\ holder = NoHolder
        /\\ waiters = {}
Next == UNCHANGED vars
MutexSafe == /\\ (holder = NoHolder) \\/ (holder \\in Procs)
             /\\ holder \\notin waiters
TypeOK == /\\ holder \\in (Procs \\cup {NoHolder})
          /\\ waiters \\subseteq Procs
          /\\ MutexSafe
================================
"""


def test_typeok_is_inductive():
    """Case A: TypeOK (x in 0..3) is preserved by the mod-4 increment."""
    result = check_inductive(_BOUNDED_COUNTER, "TypeOK")
    assert isinstance(result, InductivenessResult)
    assert result.error is None, f"unexpected tooling error: {result.error}"
    assert result.inductive is True
    assert result.cti is None


def test_bad_invariant_is_not_inductive_with_cti():
    """Case B: x < 3 is not inductive; TLC must return a CTI trace."""
    result = check_inductive(_BOUNDED_COUNTER_BAD, "Bad")
    assert isinstance(result, InductivenessResult)
    assert result.error is None, f"unexpected tooling error: {result.error}"
    assert result.inductive is False
    assert result.cti is not None
    assert result.cti.strip() != ""


def test_parse_error_reports_error():
    """Case C: an unparseable module surfaces an error, not a crash."""
    result = check_inductive(_BROKEN, "TypeOK")
    assert isinstance(result, InductivenessResult)
    assert result.inductive is False
    assert result.error is not None
    assert result.error.strip() != ""


def test_inductiveness_cfg_disables_deadlock_checking():
    cfg = _build_cfg("TypeOK", "TypeOK", _BOUNDED_COUNTER)

    assert "CHECK_DEADLOCK FALSE" in cfg


def test_typeok_with_helper_conjunct_is_still_enumerable():
    result = check_inductive(_HELPER_TYPEOK, "TypeOK")

    assert isinstance(result, InductivenessResult)
    assert result.error is None, f"unexpected tooling error: {result.error}"
    assert result.inductive is True


def test_injected_ind_init_preserves_continuation_indentation():
    proof_module = _inject_ind_init(
        _BOUNDED_COUNTER,
        "/\\ holder \\in 0..2\n         /\\ \\A s, t \\in 0..2 :\n              (s = t) => TRUE",
    )

    assert "IndInit_ChatTLA ==\n" in proof_module
    assert "             (s = t) => TRUE" in proof_module


def test_subseteq_clause_rewrite_parenthesizes_interval_rhs():
    clause = _rewrite_enumerable_clause("req", "/\\ req \\subseteq 1..N")

    assert clause == "/\\ req \\in (SUBSET (1..N))"
