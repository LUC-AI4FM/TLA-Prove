import importlib

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


def test_benchmark_default_chattla_model_honors_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CHATTLA_MODEL", "chattla:20b-fc128best")

    import src.inference.benchmark as benchmark_module

    reloaded = importlib.reload(benchmark_module)

    try:
        assert reloaded._MODELS["chattla"] == "chattla:20b-fc128best"
    finally:
        monkeypatch.delenv("CHATTLA_MODEL", raising=False)
        importlib.reload(benchmark_module)
