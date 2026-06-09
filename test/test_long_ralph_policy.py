from src.rlvr_canary.long_ralph_policy import (
    LongRunStep,
    pass_curve,
    should_stop,
)


def _step(
    n: int,
    *,
    score: float = 0.0,
    phase: str = "tlc",
    signature: str = "err",
    spec_hash: str = "spec",
    success: bool = False,
    malformed: bool = False,
) -> LongRunStep:
    return LongRunStep(
        iteration=n,
        score=score,
        phase=phase,
        failure_signature=signature,
        spec_hash=spec_hash,
        success=success,
        malformed=malformed,
    )


def test_should_stop_immediately_on_success():
    decision = should_stop([_step(1, success=True)], max_iters=64)

    assert decision.stop is True
    assert decision.reason == "success"


def test_should_stop_on_absolute_watchdog():
    steps = [_step(i, score=i / 100.0, signature=f"err-{i}") for i in range(1, 6)]

    decision = should_stop(steps, max_iters=5)

    assert decision.stop is True
    assert decision.reason == "max_iters"


def test_should_not_stop_after_repeated_failure_signature():
    steps = [
        _step(1, signature="sany|missing-end", spec_hash="a"),
        _step(2, signature="sany|missing-end", spec_hash="b"),
        _step(3, signature="sany|missing-end", spec_hash="c"),
    ]

    decision = should_stop(steps, repeated_signature_limit=3, max_iters=64)

    assert decision.stop is False


def test_should_not_stop_when_score_has_stalled():
    steps = [
        _step(1, score=0.10, signature="a", spec_hash="a"),
        _step(2, score=0.35, signature="b", spec_hash="b"),
        _step(3, score=0.35, signature="c", spec_hash="c"),
        _step(4, score=0.34, signature="d", spec_hash="d"),
        _step(5, score=0.35, signature="e", spec_hash="e"),
    ]

    decision = should_stop(steps, no_improvement_limit=3, max_iters=64)

    assert decision.stop is False


def test_should_not_stop_on_disabled_watchdog():
    steps = [_step(i, score=i / 100.0, signature=f"err-{i}") for i in range(1, 6)]

    decision = should_stop(steps, max_iters=0)

    assert decision.stop is False


def test_should_stop_on_repeated_malformed_generations():
    steps = [
        _step(1, malformed=True, signature="no-module", spec_hash="a"),
        _step(2, malformed=True, signature="no-module", spec_hash="b"),
    ]

    decision = should_stop(steps, malformed_limit=2, max_iters=64)

    assert decision.stop is True
    assert decision.reason == "malformed_output"


def test_pass_curve_counts_success_at_and_after_iteration():
    rows = [
        {"success": True, "iterations": 2},
        {"success": True, "iterations": 9},
        {"success": False, "iterations": 64},
    ]

    curve = pass_curve(rows, cutoffs=(1, 3, 8, 15, 20))

    assert curve == {
        "pass@1": 0.0,
        "pass@3": 1 / 3,
        "pass@8": 1 / 3,
        "pass@15": 2 / 3,
        "pass@20": 2 / 3,
    }
