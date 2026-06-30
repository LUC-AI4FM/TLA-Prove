from src.training.self_improve import fix_tla_syntax


def test_fix_tla_syntax_repairs_common_benchmark_parser_artifacts() -> None:
    spec = """---- MODULE MutualExclusion ----
VARIABLES procState (* state *), Critical, procState
Idle == "idle"
Critical == "critical"
Init ==
    /\\ procState = [p \\in 1 .. N |-> > Idle]
TRY(p) ==
    /\\ UNCHANGED[UNUSED(procState)]
    /\\ procState' = [procState EXCEPT ![p]'= Critical]
Spec == Init /\\ []_(vars)( Next )
====
"""

    result = fix_tla_syntax(spec)

    assert "removed stray > after |->" in result.fixes_applied
    assert "removed invalid prime from EXCEPT selector" in result.fixes_applied
    assert "normalized malformed Spec temporal formula" in result.fixes_applied
    assert "rewrote bracketed UNCHANGED form" in result.fixes_applied
    assert "cleaned single-line VARIABLES declaration" in result.fixes_applied
    assert "VARIABLES procState" in result.fixed_spec
    assert "Critical, procState" not in result.fixed_spec
    assert "|-> >" not in result.fixed_spec
    assert "![p]'=" not in result.fixed_spec
    assert "UNCHANGED[" not in result.fixed_spec
    assert "Spec == Init /\\ [][Next]_vars" in result.fixed_spec


def test_fix_tla_syntax_rewrites_constdef_and_uppercase_equal_definitions() -> None:
    spec = """---- MODULE DiningPhilosophers ----
CONSTDEF
    ParticipantSet == [p \\in Participants |-> p]
STATE_THINKING = 1
_STATE_EATING_ = 3
====
"""

    result = fix_tla_syntax(spec)

    assert "removed CONSTDEF pseudo-keyword" in result.fixes_applied
    assert "normalized top-level = definitions to ==" in result.fixes_applied
    assert "CONSTDEF" not in result.fixed_spec
    assert "STATE_THINKING == 1" in result.fixed_spec
    assert "_STATE_EATING_ == 3" in result.fixed_spec


def test_fix_tla_syntax_normalizes_planned_spec_update_and_initializer_forms() -> None:
    spec = """---- MODULE MutexAlgorithm ----
CONSTANT N \\* number of processes, N
VARIABLES pc, queue
Init ==
   /\\ pc = <<[x |-> "idle"] : x \\in 1 .. N>>
Acquire(i) ==
   /\\ pc'[i] = "critical"
   /\\ phase : STATES
   /\\ x #= y
   /\\ z /= w
   /\\ Unchanged(queue)
   /\\ pc' = [pc EXCEPT ![i] = @("trying")]
====
"""

    result = fix_tla_syntax(spec)

    assert "cleaned single-line CONSTANTS declaration" in result.fixes_applied
    assert "rewrote tuple-comprehension function initializer" in result.fixes_applied
    assert "rewrote indexed prime assignment as EXCEPT update" in result.fixes_applied
    assert "normalized colon membership conjuncts" in result.fixes_applied
    assert "normalized pseudo-inequality operators" in result.fixes_applied
    assert "normalized lowercase Unchanged operator" in result.fixes_applied
    assert "removed @(...) wrapper in EXCEPT updates" in result.fixes_applied
    assert 'CONSTANT N' in result.fixed_spec
    assert '\\* number of processes' not in result.fixed_spec
    assert 'pc = [x \\in 1 .. N |-> "idle"]' in result.fixed_spec
    assert 'pc\' = [pc EXCEPT ![i] = "critical"]' in result.fixed_spec
    assert '/\\ phase \\in STATES' in result.fixed_spec
    assert 'x # y' in result.fixed_spec
    assert 'z # w' in result.fixed_spec
    assert 'UNCHANGED queue' in result.fixed_spec
    assert '@("trying")' not in result.fixed_spec
    assert 'EXCEPT ![i] = "trying"' in result.fixed_spec


def test_fix_tla_syntax_removes_init_primes_and_alternate_function_initializer_shape() -> None:
    spec = """---- MODULE MutexAlgorithm ----
VARIABLES pc, queue
Init ==
   /\\ pc' = <<[j |-> "idle" : j \\in 1 .. N]>>
   /\\ queue' = <<>>
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote tuple-comprehension function initializer" in result.fixes_applied
    assert "removed primed assignments from Init" in result.fixes_applied
    assert "pc = [j \\in 1 .. N |-> \"idle\" ]" in result.fixed_spec
    assert "/\\ queue = <<>>" in result.fixed_spec


def test_fix_tla_syntax_removes_stray_at_prefix_in_except_rhs() -> None:
    spec = """---- MODULE MutexAlgorithm ----
VARIABLES pc
Next ==
   /\\ pc' = [pc EXCEPT ![i] = @"critical"]
====
"""

    result = fix_tla_syntax(spec)

    assert "removed @(...) wrapper in EXCEPT updates" in result.fixes_applied
    assert '@"critical"' not in result.fixed_spec
    assert 'EXCEPT ![i] = "critical"' in result.fixed_spec
