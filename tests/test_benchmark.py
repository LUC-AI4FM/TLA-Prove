from src.inference.benchmark import score_structural


def test_score_structural_returns_zero_for_unparseable_spec() -> None:
    spec = r"""---- MODULE Broken ----
EXTENDS Naturals
VARIABLES x
Init ==
    /\ x = 0
Next ==
    /\ x' = x + 1
Spec ==
    Init /\\ [][Next]_vars
TypeOK ==
    x \\in 0..10
CONSTDEF
====
"""

    score = score_structural(spec, ["TypeOK"], parse_ok=False)

    assert score == 0.0
