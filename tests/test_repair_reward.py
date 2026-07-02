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


def test_reward_sample_log_writes_jsonl(tmp_path, monkeypatch):
    import json as _json

    import src.rlvr_canary.repair_reward as rr

    log_path = tmp_path / "samples.jsonl"
    monkeypatch.setattr(rr, "_SAMPLE_LOG_PATH", str(log_path))
    monkeypatch.setattr(rr, "_SAMPLE_LOG_LIMIT", 2)
    monkeypatch.setattr(rr, "_sample_log_count", 0)
    monkeypatch.setattr(rr, "_grade_one", lambda text: 0.5)

    rewards = rr.repair_reward(
        prompts=["<!-- repair:x --> p1", "<!-- repair:x --> p2", "<!-- repair:x --> p3"],
        completions=["---- MODULE A ----", "---- MODULE B ----", "---- MODULE C ----"],
    )

    assert len(rewards) == 3
    lines = [_json.loads(l) for l in log_path.read_text().splitlines()]
    assert len(lines) == 2  # capped by limit
    assert lines[0]["after"] == 0.5
    assert "completion_head" in lines[0]


def test_aux_structure_score_orders_near_miss_above_garbage(monkeypatch):
    import src.rlvr_canary.repair_reward as rr

    monkeypatch.setattr(rr, "_grade_one", lambda text: 0.0)
    near_miss = (
        "---- MODULE M ----\nInit == x = 0\nNext == x' = x\n"
        "TypeOK == x \\in Nat\n===="
    )
    garbage = "I think the answer involves considering the spec."

    rewards = rr.repair_reward(
        prompts=["<!-- repair:x --> p", "<!-- repair:x --> p"],
        completions=[near_miss, garbage],
    )

    assert rewards[0] > rewards[1]
    # Shaping must stay strictly below the improvement floor (~0.206)
    assert all(r < 0.206 for r in rewards)


def test_aux_structure_score_never_applied_on_parse_success(monkeypatch):
    import src.rlvr_canary.repair_reward as rr

    monkeypatch.setattr(rr, "_grade_one", lambda text: 0.5)
    rewards = rr.repair_reward(
        prompts=["<!-- repair:x --> p"],
        completions=["---- MODULE M ----\nInit == TRUE\n===="],
    )
    # before falls back to 0.0, after 0.5 -> improvement branch, no aux cap
    assert rewards[0] >= 0.206
