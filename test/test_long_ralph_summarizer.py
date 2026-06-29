import json

from scripts.summarize_long_ralph_run import compact_reason, load_steps, summarize_step


def test_load_steps_accepts_streamed_step_events(tmp_path):
    path = tmp_path / "step_events.jsonl"
    path.write_text(
        json.dumps({
            "prompt_id": "p1",
            "step": {
                "iteration": 7,
                "phase": "adequacy",
                "failure_family": "weak_fairness",
                "judge_reason": "Missing fairness.",
                "semantic": {
                    "properties_checked": 1,
                    "properties_declared": True,
                    "property_names": ["EventuallyHolds"],
                },
            },
        }) + "\n",
        encoding="utf-8",
    )

    steps = load_steps(path)

    assert steps[0]["iteration"] == 7
    assert compact_reason(steps[0]) == "Missing fairness."
    assert summarize_step(steps[0])["properties_checked"] == 1
