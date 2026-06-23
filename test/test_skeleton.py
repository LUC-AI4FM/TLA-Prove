"""Tests for deterministic codegen of a TLAPS safety-proof skeleton."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.prover.skeleton import SafetySkeletonSpec, safety_proof_skeleton


def _case_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("<2>") and "CASE" in ln]


def test_case_count_with_unchanged():
    spec = SafetySkeletonSpec(
        invariant_name="Inv",
        next_action_names=["Request(p)", "Enter(p)", "Exit(p)"],
    )
    cases = _case_lines(safety_proof_skeleton(spec))
    assert len(cases) == len(spec.next_action_names) + 1  # +1 for UNCHANGED


def test_case_count_without_unchanged():
    spec = SafetySkeletonSpec(
        invariant_name="Inv",
        next_action_names=["Request(p)", "Enter(p)"],
        include_unchanged_case=False,
    )
    cases = _case_lines(safety_proof_skeleton(spec))
    assert len(cases) == len(spec.next_action_names)
    assert "UNCHANGED" not in safety_proof_skeleton(spec)


def test_params_kept_in_case_stripped_in_def():
    spec = SafetySkeletonSpec(invariant_name="Inv", next_action_names=["Request(p)"])
    text = safety_proof_skeleton(spec)
    assert "<2>1. CASE Request(p)" in text
    assert "BY DEF Inv, Request" in text
    assert "BY DEF Inv, Request(p)" not in text


def test_property_step_present():
    spec = SafetySkeletonSpec(
        invariant_name="Inv",
        next_action_names=["Request(p)", "Enter(p)"],
        property_name="MutualExclusion",
    )
    text = safety_proof_skeleton(spec)
    assert "<1>3. Inv => MutualExclusion" in text
    assert "BY DEF Inv, MutualExclusion" in text
    assert "BY <1>1, <1>2, <1>3, PTL DEF Spec" in text


def test_property_step_absent():
    spec = SafetySkeletonSpec(
        invariant_name="Inv",
        next_action_names=["Request(p)", "Enter(p)"],
        property_name=None,
    )
    text = safety_proof_skeleton(spec)
    assert "<1>3." not in text
    assert "MutualExclusion" not in text
    assert "BY <1>1, <1>2, PTL DEF Spec" in text


def test_unchanged_case_uses_vars_name():
    spec = SafetySkeletonSpec(
        invariant_name="Inv",
        next_action_names=["Request(p)"],
        vars_name="myvars",
    )
    text = safety_proof_skeleton(spec)
    assert "CASE UNCHANGED myvars" in text
    assert "BY DEF Inv, myvars" in text


def test_inner_qed_cites_all_sublabels():
    spec = SafetySkeletonSpec(
        invariant_name="Inv",
        next_action_names=["Request(p)", "Enter(p)", "Exit(p)"],
    )
    text = safety_proof_skeleton(spec)
    # 3 actions + UNCHANGED => labels <2>1..<2>4
    assert "<2> QED" in text
    assert "BY <2>1, <2>2, <2>3, <2>4 DEF Next" in text


def test_outer_qed_ends_with_ptl_def_spec():
    spec = SafetySkeletonSpec(invariant_name="Inv", next_action_names=["Request(p)"])
    text = safety_proof_skeleton(spec)
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    assert lines[-1].strip().endswith("PTL DEF Spec")


def test_full_two_action_property_shape():
    spec = SafetySkeletonSpec(
        invariant_name="Inv",
        next_action_names=["Request(p)", "Enter(p)"],
        property_name="MutualExclusion",
    )
    expected = (
        "<1>1. Init => Inv\n"
        "  BY DEF Init, Inv\n"
        "<1>2. Inv /\\ [Next]_vars => Inv'\n"
        "  <2>1. CASE Request(p)\n"
        "    BY DEF Inv, Request\n"
        "  <2>2. CASE Enter(p)\n"
        "    BY DEF Inv, Enter\n"
        "  <2>3. CASE UNCHANGED vars\n"
        "    BY DEF Inv, vars\n"
        "  <2> QED\n"
        "    BY <2>1, <2>2, <2>3 DEF Next\n"
        "<1>3. Inv => MutualExclusion\n"
        "  BY DEF Inv, MutualExclusion\n"
        "<1> QED\n"
        "  BY <1>1, <1>2, <1>3, PTL DEF Spec"
    )
    assert safety_proof_skeleton(spec) == expected
