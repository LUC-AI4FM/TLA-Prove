"""Tests for the deterministic TLAPS fact retriever (src/prover/fact_library.py)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.prover.fact_library import FACTS, Fact, suggest_facts


def _names(facts):
    return [f.name for f in facts]


def test_catalog_is_nonempty_and_well_typed():
    assert len(FACTS) >= 10
    assert all(isinstance(f, Fact) for f in FACTS)
    assert all(f.keywords for f in FACTS)


def test_cardinality_error_suggests_finite_set_fact():
    result = suggest_facts("TLC error: Cardinality of ... is not defined")
    assert any(name.startswith("FS_") for name in _names(result))


def test_enabled_obligation_suggests_enabled_rules():
    result = suggest_facts("could not prove ENABLED <<DetectTermination>>_vars")
    names = _names(result)
    assert "ENABLEDrules" in names or "ExpandENABLED" in names


def test_temporal_qed_suggests_ptl():
    result = suggest_facts("QED step: [](P => <>Q) temporal reasoning")
    assert "PTL" in _names(result)


def test_induction_obligation_suggests_naturals_induction():
    result = suggest_facts("prove by induction over Nat that Measure decreases")
    naturals = {f.name for f in FACTS if f.module == "NaturalsInduction"}
    assert any(name in naturals for name in _names(result))


def test_arithmetic_obligation_suggests_smt():
    result = suggest_facts("simple arithmetic obligation 2 + 2 = 4")
    assert "SMT" in _names(result)


def test_k_limit_respected():
    assert len(suggest_facts("ENABLED temporal induction cardinality arithmetic", k=3)) <= 3
    assert len(suggest_facts("ENABLED temporal induction cardinality arithmetic", k=1)) <= 1
    assert len(suggest_facts("anything at all")) <= 5


def test_returns_fact_objects_not_names():
    result = suggest_facts("ENABLED action enabled")
    assert all(isinstance(f, Fact) for f in result)
