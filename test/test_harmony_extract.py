"""Tests for harmony final-channel extraction (Stage 0 of the prover rewrite).

Root cause being fixed: prover generations were decoded with
``skip_special_tokens=True`` and then split on the literal word ``"final"``,
which also appears in analysis prose ("the *final* theorem"). So the analysis
reasoning leaked into the extracted proof and SANY returned ``parse_error``.
See the old ``strip_to_proof`` in scripts/diagnose_prover.py and the duplicated
logic in scripts/eval_prover_checkpoint.py and src/training/tlaps_eval_callback.py.

The fix keys extraction on the harmony channel structure (or, in the degraded
no-marker form, on the TLAPS proof anchor ``^<n>``) — never on the word "final".
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.harmony_extract import extract_final_channel


def test_final_word_in_analysis_prose_is_not_a_boundary():
    # The core bug: "final" occurs inside the analysis channel as ordinary prose.
    raw = (
        "<|channel|>analysis<|message|>We need to write the TLAPS proof for the "
        "final theorem OGLiveness. The theorem states OGSpec => <>Q.<|end|>"
        "<|start|>assistant<|channel|>final<|message|>"
        "<1>1. Init => Inv\n  BY DEF Init, Inv\n<1> QED\n  BY PTL<|return|>"
    )
    res = extract_final_channel(raw)
    assert res.status == "ok"
    assert res.proof.startswith("<1>1. Init => Inv")
    assert "We need to write" not in res.proof


def test_final_only_generation():
    raw = (
        "<|channel|>final<|message|><1>1. Init => Inv  BY DEF Init\n"
        "<1> QED  BY PTL<|return|>"
    )
    res = extract_final_channel(raw)
    assert res.status == "ok"
    assert res.proof.startswith("<1>1.")


def test_truncated_analysis_only_is_no_final():
    # Model exhausted the token budget in analysis and never emitted `final`.
    raw = (
        "<|channel|>analysis<|message|>We need to write the TLAPS proof for the "
        "final theorem. First we establish the inductive invariant and then ..."
    )
    res = extract_final_channel(raw)
    assert res.status == "no_final"
    assert res.proof == ""


def test_degraded_no_markers_uses_proof_anchor_not_final_word():
    # Legacy skip_special_tokens=True form: channel headers became bare words.
    raw = (
        "analysisWe need to write the proof for the final theorem.\n"
        "<1>1. Init => Inv\n  BY DEF Init, Inv\n<1> QED  BY PTL"
    )
    res = extract_final_channel(raw)
    assert res.status == "ok"
    assert res.proof.startswith("<1>1. Init => Inv")
    assert "We need to write" not in res.proof


def test_degraded_truncated_without_proof_is_no_final():
    raw = "analysisWe need to write the final theorem proof; first the invariant ..."
    res = extract_final_channel(raw)
    assert res.status == "no_final"
    assert res.proof == ""


def test_degraded_final_glued_to_first_bullet_keeps_first_step():
    # Real cached form (FindHighest.tla): skip_special_tokens=True glued the
    # channel word "final" to the first proof bullet with no newline, so a
    # line-anchored search silently dropped the <1>a step.
    raw = (
        "analysisWe reason about it.final<1>a. Init => InductiveInvariant\n"
        "  BY DEFS Init, InductiveInvariant\n"
        "<1>b. InductiveInvariant /\\ UNCHANGED vars => InductiveInvariant'\n"
        "  BY DEFS InductiveInvariant, vars\n<1> QED  BY PTL"
    )
    res = extract_final_channel(raw)
    assert res.status == "ok"
    assert res.proof.startswith("<1>a. Init => InductiveInvariant")
