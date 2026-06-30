from src.rlvr_canary.repair_reward import _shape_reward


def test_shape_reward_penalizes_regressions() -> None:
    reward = _shape_reward(0.40, 0.20)

    assert reward == 0.0


def test_shape_reward_gives_baseline_for_no_change() -> None:
    reward = _shape_reward(0.40, 0.405)

    assert reward == 0.15


def test_shape_reward_adds_transition_bonuses() -> None:
    reward = _shape_reward(0.05, 1.0)

    assert reward == 1.0


def test_shape_reward_caps_at_one() -> None:
    reward = _shape_reward(0.0, 2.0)

    assert reward == 1.0
