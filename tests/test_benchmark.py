import importlib
import json
from pathlib import Path

from src.inference.benchmark import (
    _run_single_attempt,
    benchmark_execution_metadata,
    benchmark_metadata_path,
    score_structural,
)


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


def test_benchmark_execution_metadata_records_mode_and_sidecar_path(tmp_path: Path) -> None:
    output_csv = tmp_path / "benchmark_results_probe.csv"

    payload = benchmark_execution_metadata(
        output_csv=output_csv,
        models=["chattla:20b-fc128best"],
        use_self_correct=True,
        attempts=3,
        use_plan=True,
        limit=2,
        problem_ids=["BM001", "BM002"],
    )

    assert payload["source_csv"] == "benchmark_results_probe.csv"
    assert payload["execution"] == {
        "self_correct": True,
        "use_plan": True,
        "attempts": 3,
        "inference_mode": "self-correct+plan-then-spec+best-of-3",
    }
    assert benchmark_metadata_path(output_csv) == tmp_path / "benchmark_results_probe.csv.meta.json"


def test_run_single_attempt_forwards_use_plan_during_self_correct(monkeypatch) -> None:
    class _Semantic:
        init_present = False
        next_present = False
        init_level_ok = False
        next_level_ok = False
        invariants_declared = False
        tlc_depth1_ok = False
        partial_credit = 0.0

    class _TLCResult:
        tier = "bronze"
        semantic = _Semantic()

    class _FakeClient:
        def __init__(self) -> None:
            self._last_plan_used = False
            self.calls: list[dict[str, object]] = []

        def validate_and_generate(self, description: str, max_retries: int = 3, use_plan: bool = False, module_name=None):
            self.calls.append(
                {
                    "description": description,
                    "max_retries": max_retries,
                    "use_plan": use_plan,
                    "module_name": module_name,
                }
            )
            self._last_plan_used = use_plan
            return "---- MODULE Test ----\n====\n", "bronze"

    monkeypatch.setattr("src.validators.tlc_validator.validate_string", lambda spec, module_name=None: _TLCResult())

    client = _FakeClient()
    result = _run_single_attempt(
        {
            "id": "BM001",
            "name": "Mutual Exclusion",
            "description": "desc",
            "expected_invariants": [],
        },
        client,
        use_self_correct=True,
        use_plan=True,
    )

    assert client.calls[0]["use_plan"] is True
    assert result["plan_used"] is True
