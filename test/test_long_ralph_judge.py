from scripts.collect_long_ralph_trajectories import (
    _apply_unified_diff,
    _extract_unified_diff,
    _patched_spec_from_response,
    audit_candidate,
    acceptance_frontier_key,
    build_repair_context,
    branch_focuses_for_family,
    branch_assignment_conflicts,
    classify_failure_family,
    flatten_pairs,
    frontier_stall_count,
    line_numbered_error_excerpt,
    model_recipe,
    objective_score,
    parse_judge_response,
    same_failure_family_tail_count,
    select_repair_parent,
    select_branch_result,
    selected_final_step,
    semantic_repair_hint,
    should_stop_for_frontier_stall,
    should_stop_for_semantic_stall,
    should_start_parallel_branches,
    spec_shape_hint,
    stuck_rewrite_instruction,
    syntax_repair_hint,
    _trim_context,
    _validator_diagnostics,
)
from argparse import Namespace


def test_extract_unified_diff_from_fenced_response():
    response = """```diff
--- previous.tla
+++ repaired.tla
@@ -1,3 +1,3 @@
 ---- MODULE Test ----
-x == 1
+x == 2
 ====
```"""

    diff = _extract_unified_diff(response)

    assert diff.startswith("--- previous.tla")
    assert "@@ -1,3 +1,3 @@" in diff


def test_apply_unified_diff_updates_spec():
    original = "---- MODULE Test ----\nx == 1\n===="
    diff = """--- previous.tla
+++ repaired.tla
@@ -1,3 +1,3 @@
 ---- MODULE Test ----
-x == 1
+x == 2
 ====
"""

    repaired = _apply_unified_diff(original, diff)

    assert repaired == "---- MODULE Test ----\nx == 2\n===="


def test_patched_spec_from_response_returns_none_for_non_applying_diff():
    original = "---- MODULE Test ----\nx == 1\n===="
    response = """```diff
--- previous.tla
+++ repaired.tla
@@ -1,3 +1,3 @@
 ---- MODULE Test ----
-x == 7
+x == 2
 ====
```"""

    assert _patched_spec_from_response(original, response) is None


def test_parse_judge_response_accepts_exact_ok():
    ok, reason = parse_judge_response("OK")

    assert ok is True
    assert reason == ""


def test_parse_judge_response_rejects_with_reason():
    ok, reason = parse_judge_response(
        "NOT_OK: The spec models a simple flag, but the request requires FIFO wakeups."
    )

    assert ok is False
    assert "FIFO wakeups" in reason


def test_parse_judge_response_treats_ambiguous_text_as_reject():
    ok, reason = parse_judge_response("This looks mostly fine, maybe acceptable.")

    assert ok is False
    assert "ambiguous" in reason.lower()


def test_build_repair_context_includes_final_judge_reason():
    step = {
        "iteration": 3,
        "tier": "gold",
        "phase": "adequacy",
        "score": 1.0,
        "judge_ok": False,
        "judge_reason": "The spec ignores waiter accounting.",
        "diagnostics": "The spec ignores waiter accounting.",
    }
    verdict = {
        "tier": "gold",
        "phase": "adequacy",
        "score": 1.0,
        "diamond": True,
        "judge_ok": False,
        "judge_reason": "The spec ignores waiter accounting.",
        "diagnostics": "The spec ignores waiter accounting.",
        "semantic": {"partial_credit": 1.0},
    }

    context = build_repair_context(verdict, [step])

    assert "Final model verifier rejection" in context
    assert "waiter accounting" in context
    assert "Recent attempts" in context


def test_validator_diagnostics_preserves_error_header_when_raw_is_long():
    raw = "warning text " * 400 + "tail marker"

    diagnostics = _validator_diagnostics(
        ["Error: Invariant TypeOK is violated."],
        raw,
        limit=180,
    )

    assert diagnostics.startswith("Error: Invariant TypeOK is violated.")
    assert "tail marker" in diagnostics


def test_trim_context_preserves_header_and_tail():
    text = "HEADER\n" + ("middle\n" * 1000) + "TAIL"

    trimmed = _trim_context(text, limit=200)

    assert trimmed.startswith("HEADER")
    assert "...[truncated]..." in trimmed
    assert trimmed.endswith("TAIL")


def test_line_numbered_error_excerpt_uses_sany_line_number():
    spec = "\n".join(f"line {i}" for i in range(1, 12))
    diagnostics = 'Encountered "Beginning of definition" at line 7, column 1.'

    excerpt = line_numbered_error_excerpt(spec, diagnostics, radius=2)

    assert "0005: line 5" in excerpt
    assert "0007: line 7" in excerpt
    assert "0009: line 9" in excerpt


def test_stuck_rewrite_instruction_detects_repeated_sany_failure():
    steps = [
        {
            "phase": "sany",
            "spec_hash": "same",
            "failure_signature": "sany|same parse error",
        }
        for _ in range(4)
    ]

    instruction = stuck_rewrite_instruction(steps)

    assert "STUCK SYNTAX REWRITE MODE" in instruction


def test_syntax_repair_hint_explains_if_action_case():
    hint = syntax_repair_hint(
        "P == IF holder = 0 THEN /\\ holder' = 1",
        "Residual stack trace follows: IF THEN ELSE starting at line 17.",
    )

    assert "guarded disjuncts" in hint
    assert "Every IF must have" in hint


def test_syntax_repair_hint_explains_fairness_syntax():
    hint = syntax_repair_hint(
        "Spec == Init /\\ [][Next]_vars /\\ WF_A(A)",
        "Level error in applying operator $WF",
    )

    assert "WF_vars(ActionName)" in hint
    assert "WF_ActionName" in hint


def test_syntax_repair_hint_explains_precedence_conflict():
    hint = syntax_repair_hint(
        "P == /\\ (holder = 0 /\\ holder' = p) \\/ (holder # 0 /\\ waiters' = waiters + 1)",
        "Precedence conflict between ops \\lor and \\land.",
    )

    assert "guarded disjunctions" in hint
    assert "avoid mixing" in hint


def test_syntax_repair_hint_explains_cardinality_extension():
    hint = syntax_repair_hint(
        "AtMostOneHolder == Cardinality({p \\in Proc : pc[p] = \"holding\"}) <= 1",
        "Unknown operator: `Cardinality'.",
    )

    assert "FiniteSets" in hint
    assert "quantifiers" in hint


def test_syntax_repair_hint_explains_sequence_range_misuse():
    hint = syntax_repair_hint(
        "WaitersAreWaiting == \\A p \\in Proc : p \\in Range(waiters)",
        "The operator Range requires 0 arguments.",
    )

    assert "sequence-to-set" in hint
    assert "\\E i \\in 1..Len(waiters)" in hint


def test_syntax_repair_hint_explains_false_assumption():
    hint = syntax_repair_hint(
        "CONSTANTS Proc\nASSUME Proc \\subseteq 1..5",
        "Error: Assumption line 7, col 8 to line 7, col 29 is false.",
    )

    assert "concrete finite definitions" in hint
    assert "remove the ASSUME" in hint


def test_semantic_repair_hint_pushes_process_liveness_modeling():
    hint = semantic_repair_hint({
        "phase": "adequacy",
        "judge_reason": "Missing liveness property and explicit process behavior for waiting processes.",
    })

    assert "liveness/progress" in hint
    assert "pc \\in [Proc" in hint


def test_semantic_repair_hint_flags_vacuous_overrestricted_model():
    hint = semantic_repair_hint({
        "phase": "adequacy",
        "judge_reason": (
            "The safety property is vacuous because CanAcquire is too strong and "
            "the spec does not accurately model release by the holder."
        ),
    })

    assert "over-restricting" in hint
    assert "current holder" in hint


def test_semantic_repair_hint_flags_static_diamond_model():
    hint = semantic_repair_hint({
        "phase": "adequacy",
        "diagnostics": "TLC passed, but diamond failed.",
        "semantic": {"distinct_states": 1, "total_actions": 0, "action_coverage": 0.0},
    })

    assert "vacuous or static" in hint
    assert "state-changing actions" in hint
    assert "Action-coverage" in hint


def test_spec_shape_hint_flags_constants_assume_and_unused_fairness():
    spec = """---- MODULE BinarySemaphore ----
CONSTANTS Proc
ASSUME Proc \\subseteq 1..5
VARIABLES holder
vars == <<holder>>
Spec == Init /\\ [][Next]_vars
SpecWithFairness == Spec /\\ WF_vars(Next)
===="""

    hint = spec_shape_hint(spec, {"phase": "tlc"})

    assert "CONSTANTS + ASSUME" in hint
    assert "SpecWithFairness" in hint


def test_branch_assignment_conflicts_detects_common_unchanged_conflict():
    spec = """P(p) == /\\ holder' = p
          /\\ UNCHANGED <<holder, waiters>>
"""

    assert branch_assignment_conflicts(spec) == {"holder"}


def test_branch_assignment_conflicts_ignores_separate_action_branches():
    spec = """P(p) ==
    \\/ /\\ pc[p] = "idle"
       /\\ holder = 0
       /\\ pc' = [pc EXCEPT ![p] = "holding"]
       /\\ holder' = p
       /\\ UNCHANGED <<waiters>>
    \\/ /\\ pc[p] = "idle"
       /\\ holder # 0
       /\\ waiters' = Append(waiters, p)
       /\\ UNCHANGED <<holder>>
"""

    assert branch_assignment_conflicts(spec) == set()


def test_model_recipe_for_semaphore_supplies_concrete_scaffold():
    recipe = model_recipe("binary semaphore with blocking waiters", "BinarySemaphore", "")

    assert "Proc == 1..3" in recipe
    assert "WF_vars(Next)" in recipe


def test_classify_failure_family_declared_unchecked_liveness():
    family = classify_failure_family({
        "success": False,
        "phase": "adequacy",
        "diagnostics": "",
        "judge_reason": "",
        "semantic": {
            "properties_declared": True,
            "properties_checked": 0,
            "total_actions": 2,
            "action_coverage": 1.0,
            "distinct_states": 3,
        },
    })

    assert family == "declared_but_unchecked_liveness"


def test_classify_failure_family_common_adequacy_basins():
    base = {
        "success": False,
        "phase": "adequacy",
        "semantic": {
            "properties_declared": False,
            "properties_checked": 0,
            "total_actions": 2,
            "action_coverage": 1.0,
            "distinct_states": 3,
        },
    }

    assert classify_failure_family(base | {
        "judge_reason": "The waiting process can starve; weak fairness is missing.",
        "diagnostics": "",
    }) == "weak_fairness"
    assert classify_failure_family(base | {
        "judge_reason": "The release operation ignores the current holder ownership.",
        "diagnostics": "",
    }) == "bad_ownership"
    assert classify_failure_family(base | {
        "judge_reason": "The safety invariant is vacuous because behavior is over-restricted.",
        "diagnostics": "",
        "semantic": base["semantic"] | {"distinct_states": 1},
    }) == "vacuous_safety"
    assert classify_failure_family(base | {
        "judge_reason": "",
        "diagnostics": "",
        "semantic": base["semantic"] | {"total_actions": 0, "action_coverage": 0.0},
    }) == "zero_action_coverage"
    assert classify_failure_family(base | {
        "judge_reason": "A process can release without being the current holder.",
        "diagnostics": "",
        "semantic": base["semantic"] | {"total_actions": 0, "action_coverage": 0.0},
    }) == "bad_ownership"
    assert classify_failure_family(base | {
        "judge_reason": "Waiting processes can starve; fairness is missing.",
        "diagnostics": "",
        "semantic": base["semantic"] | {"total_actions": 0, "action_coverage": 0.0},
    }) == "weak_fairness"


def test_classify_failure_family_syntax_and_tlc():
    assert classify_failure_family({
        "success": False,
        "phase": "sany",
        "diagnostics": "Precedence conflict between ops \\lor and \\land.",
        "judge_reason": "",
        "semantic": {},
    }) == "syntax_precedence"
    assert classify_failure_family({
        "success": False,
        "phase": "tlc",
        "diagnostics": "Error: Assumption line 7 is false.",
        "judge_reason": "",
        "semantic": {},
    }) == "false_assumption"
    assert classify_failure_family({
        "success": False,
        "phase": "tlc",
        "diagnostics": (
            "Error: TLC requires V not to take any argument. "
            "Use the -XX:+UseParallelGC property for better throughput."
        ),
        "judge_reason": "",
        "semantic": {},
    }) == "tlc"
    assert classify_failure_family({
        "success": False,
        "phase": "tlc",
        "diagnostics": "Error: Temporal properties were violated.",
        "judge_reason": "",
        "semantic": {},
    }) == "property_violation"


def test_semantic_stall_stop_counts_same_adequacy_family():
    steps = [
        {"phase": "adequacy", "success": False, "failure_family": "weak_fairness"}
        for _ in range(4)
    ]
    args = Namespace(semantic_stall_stop=True, max_same_failure_family_iters=4)

    assert same_failure_family_tail_count(steps) == 4
    assert should_stop_for_semantic_stall(steps, args) is True


def test_semantic_stall_stop_ignores_disabled_and_non_adequacy():
    args = Namespace(semantic_stall_stop=False, max_same_failure_family_iters=2)
    steps = [
        {"phase": "adequacy", "success": False, "failure_family": "weak_fairness"},
        {"phase": "adequacy", "success": False, "failure_family": "weak_fairness"},
    ]
    assert should_stop_for_semantic_stall(steps, args) is False

    args.semantic_stall_stop = True
    steps[-1]["phase"] = "tlc"
    assert should_stop_for_semantic_stall(steps, args) is False


def test_frontier_stall_stop_catches_rotating_semantic_basin():
    args = Namespace(max_frontier_stall_iters=4)
    steps = [
        {"phase": "adequacy", "tier": "gold", "score": 0.72, "success": False, "judge_ok": False, "diamond": True, "failure_family": "bad_ownership", "semantic": {"properties_declared": True, "properties_checked": 1, "distinct_states": 4, "total_actions": 2, "action_coverage": 1.0}},
        {"phase": "adequacy", "tier": "gold", "score": 0.72, "success": False, "judge_ok": False, "diamond": True, "failure_family": "weak_fairness", "semantic": {"properties_declared": True, "properties_checked": 1, "distinct_states": 4, "total_actions": 2, "action_coverage": 1.0}},
        {"phase": "adequacy", "tier": "gold", "score": 0.72, "success": False, "judge_ok": False, "diamond": True, "failure_family": "property_violation", "semantic": {"properties_declared": True, "properties_checked": 1, "distinct_states": 4, "total_actions": 2, "action_coverage": 1.0}},
        {"phase": "adequacy", "tier": "gold", "score": 0.72, "success": False, "judge_ok": False, "diamond": True, "failure_family": "bad_ownership", "semantic": {"properties_declared": True, "properties_checked": 1, "distinct_states": 4, "total_actions": 2, "action_coverage": 1.0}},
        {"phase": "adequacy", "tier": "gold", "score": 0.72, "success": False, "judge_ok": False, "diamond": True, "failure_family": "weak_fairness", "semantic": {"properties_declared": True, "properties_checked": 1, "distinct_states": 4, "total_actions": 2, "action_coverage": 1.0}},
    ]

    assert frontier_stall_count(steps) == 4
    assert should_stop_for_frontier_stall(steps, args) is True


def test_parallel_branch_trigger_uses_frontier_stall_threshold():
    args = Namespace(branch_width=5, branch_after_iters=20, branch_iters=8)
    steps = [
        {"iteration": i, "success": False, "failure_family": "property_violation"}
        for i in range(1, 22)
    ]
    for step in steps:
        step.update({
            "phase": "adequacy",
            "tier": "gold",
            "score": 0.72,
            "judge_ok": False,
            "diamond": True,
            "semantic": {"properties_declared": True, "properties_checked": 1, "distinct_states": 4, "total_actions": 2, "action_coverage": 1.0},
        })

    assert should_start_parallel_branches(steps, args, last_branch_at=0) is True
    assert should_start_parallel_branches(steps, args, last_branch_at=15) is False

    improved = steps[:-1] + [steps[-1] | {"success": True, "judge_ok": True, "phase": "success", "score": 1.0}]
    assert frontier_stall_count(improved) == 0
    assert should_start_parallel_branches(improved, args, last_branch_at=0) is False


def test_parallel_branch_focuses_prioritize_current_failure_family():
    focuses = branch_focuses_for_family("property_violation", 5)

    assert [name for name, _ in focuses] == [
        "liveness",
        "cfg",
        "queue",
        "simplify",
        "ownership",
    ]


def test_parallel_branch_focuses_handle_false_assumptions():
    focuses = branch_focuses_for_family("false_assumption", 5)

    assert [name for name, _ in focuses] == [
        "assumptions",
        "cfg",
        "simplify",
        "queue",
        "liveness",
    ]


def test_select_branch_result_prefers_success_then_score():
    losing = {
        "branch_id": "r1b1",
        "steps": [{"success": False, "judge_ok": False, "score": 1.0, "diamond": True, "tier": "gold", "phase": "adequacy", "iteration": 2}],
    }
    winning = {
        "branch_id": "r1b2",
        "steps": [{"success": True, "judge_ok": True, "score": 0.9, "diamond": True, "tier": "gold", "phase": "success", "iteration": 3}],
    }

    assert select_branch_result([losing, winning])["branch_id"] == "r1b2"


def test_selected_branch_step_prefers_best_frontier_over_last_regression():
    gold = {
        "success": False,
        "judge_ok": False,
        "score": 0.84,
        "diamond": True,
        "tier": "gold",
        "phase": "adequacy",
        "iteration": 2,
        "failure_family": "weak_fairness",
        "semantic": {
            "properties_declared": True,
            "properties_checked": 1,
            "distinct_states": 4,
            "total_actions": 2,
            "action_coverage": 1.0,
        },
    }
    regressed = gold | {
        "score": 0.1,
        "diamond": False,
        "tier": "bronze",
        "phase": "sany",
        "iteration": 3,
        "failure_family": "syntax",
        "semantic": {},
    }

    selected = selected_final_step({"branch_id": "r1b1", "steps": [gold, regressed]})

    assert selected is gold


def test_select_repair_parent_anchors_to_best_frontier_after_regression():
    gold = {
        "iteration": 4,
        "success": False,
        "judge_ok": False,
        "score": 0.84,
        "diamond": True,
        "tier": "gold",
        "phase": "adequacy",
        "failure_family": "weak_fairness",
        "semantic": {
            "properties_declared": True,
            "properties_checked": 1,
            "distinct_states": 4,
            "total_actions": 2,
            "action_coverage": 1.0,
        },
    }
    syntax = gold | {
        "iteration": 5,
        "score": 0.0,
        "diamond": False,
        "tier": "bronze",
        "phase": "sany",
        "failure_family": "syntax",
        "semantic": {},
    }

    parent = select_repair_parent([gold, syntax])

    assert parent is gold


def test_local_modeling_audit_requires_checked_liveness_when_requirement_mentions_waiting():
    ok, reason = audit_candidate(
        "A binary semaphore where blocked waiters eventually acquire.",
        "",
        "---- MODULE BinarySemaphore ----\nSpec == Init /\\ [][Next]_vars\n====",
        {
            "distinct_states": 4,
            "invariants_checked": 1,
            "trivial_invariant": False,
            "mutation_tested": True,
            "mutation_caught": True,
            "properties_declared": False,
            "properties_checked": 0,
        },
    )

    assert ok is False
    assert "liveness" in reason.lower()


def test_local_modeling_audit_accepts_checked_invariants_and_liveness_shape():
    ok, reason = audit_candidate(
        "A binary semaphore where blocked waiters eventually acquire.",
        "",
        (
            "---- MODULE BinarySemaphore ----\n"
            "Proc == 1..3\n"
            "VARIABLES pc, waiters\n"
            "Spec == Init /\\ [][Next]_vars /\\ WF_vars(Next)\n"
            "Safety == TypeOK\n"
            "WaitersEventuallyAcquire == \\A p \\in Proc : [](pc[p] = \"waiting\" => <>(pc[p] = \"holding\"))\n"
            "===="
        ),
        {
            "distinct_states": 4,
            "invariants_checked": 1,
            "trivial_invariant": False,
            "mutation_tested": True,
            "mutation_caught": True,
            "properties_declared": True,
            "properties_checked": 1,
        },
    )

    assert ok is True
    assert reason == ""


def test_objective_score_caps_gold_rejects_below_success():
    rejected = {
        "phase": "adequacy",
        "tier": "gold",
        "raw_score": 1.0,
        "judge_ok": False,
        "success": False,
        "diamond": True,
        "failure_family": "bad_ownership",
        "semantic": {
            "properties_declared": True,
            "properties_checked": 1,
            "distinct_states": 4,
            "total_actions": 2,
            "action_coverage": 1.0,
        },
    }
    accepted = rejected | {"judge_ok": True, "success": True}

    assert objective_score(rejected) < 1.0
    assert objective_score(rejected) <= 0.84
    assert objective_score(accepted) == 1.0


def test_acceptance_frontier_prefers_checked_liveness():
    unchecked = {
        "phase": "adequacy",
        "tier": "gold",
        "score": 0.60,
        "success": False,
        "judge_ok": False,
        "diamond": True,
        "failure_family": "declared_but_unchecked_liveness",
        "semantic": {
            "properties_declared": True,
            "properties_checked": 0,
            "distinct_states": 4,
            "total_actions": 2,
            "action_coverage": 1.0,
        },
    }
    checked = unchecked | {
        "score": 0.72,
        "failure_family": "weak_fairness",
        "semantic": unchecked["semantic"] | {"properties_checked": 1},
    }

    assert acceptance_frontier_key(checked) > acceptance_frontier_key(unchecked)


def test_flatten_pairs_uses_parent_iterations_for_parallel_steps():
    traj = {
        "prompt_id": "p",
        "nl": "requirement",
        "steps": [
            {
                "iteration": 1,
                "spec": "root",
                "diagnostics": "root diag",
                "repair_context": "root ctx",
                "score": 0.1,
                "tier": "bronze",
                "phase": "sany",
                "diamond": False,
                "success": False,
                "generator": "g",
            },
            {
                "iteration": 2,
                "parent_iteration": 1,
                "spec": "branch a",
                "diagnostics": "a",
                "score": 0.2,
                "tier": "silver",
                "phase": "tlc",
                "diamond": False,
                "success": False,
                "generator": "g",
            },
            {
                "iteration": 3,
                "parent_iteration": 1,
                "spec": "branch b",
                "diagnostics": "b",
                "score": 0.3,
                "tier": "gold",
                "phase": "adequacy",
                "diamond": True,
                "success": False,
                "generator": "g",
            },
        ],
    }

    pairs = flatten_pairs(traj)

    assert len(pairs) == 2
    assert [pair["broken_spec"] for pair in pairs] == ["root", "root"]
    assert [pair["repaired_spec"] for pair in pairs] == ["branch a", "branch b"]
