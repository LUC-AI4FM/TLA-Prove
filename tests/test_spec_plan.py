from src.shared.schemas.spec_plan import parse_plan


def test_parse_plan_tolerates_raw_tla_backslashes_in_json_strings() -> None:
    raw = """{
  "module_name":"MutexAlgorithm",
  "extends":["Naturals","Sequences"],
  "constants":["N"],
  "variables":["pc","queue"],
  "next_actions":[
    {
      "name":"Acquire",
      "guard":"pc[i] = \\"idle\\" /\\
        i \\in 1..N",
      "effect":"pc' = [pc EXCEPT ![i] = \\"trying\\"] /\\
        queue' = Append(queue,i)"
    }
  ],
  "invariants":[
    {
      "name":"MutualExclusion",
      "kind":"safety",
      "statement":"\\u2200 i,j \\in 1..N: (i # j) => ~(pc[i] = \\"critical\\" /\\ pc[j] = \\"critical\\")"
    }
  ]
}"""

    plan = parse_plan(raw)

    assert plan is not None
    assert plan.module_name == "MutexAlgorithm"
    assert plan.next_actions[0].name == "Acquire"
    assert "\\in 1..N" in plan.next_actions[0].guard
    assert "/\\" in plan.next_actions[0].effect


def test_parse_plan_tolerates_fenced_json_with_invalid_escapes() -> None:
    raw = """```json
{
  "module_name":"QueueSpec",
  "variables":["queue"],
  "invariants":[
    {"name":"TypeOK","kind":"type","statement":"queue \\in Seq(Nat)"}
  ]
}
```"""

    plan = parse_plan(raw)

    assert plan is not None
    assert plan.module_name == "QueueSpec"
    assert plan.invariants[0].statement == "queue \\in Seq(Nat)"
