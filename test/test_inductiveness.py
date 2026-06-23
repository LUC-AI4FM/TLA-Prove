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

from src.prover.inductiveness import check_inductive, InductivenessResult  # noqa: E402


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
