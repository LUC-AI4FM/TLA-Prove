from src.training.self_improve import fix_tla_syntax
from src.validators.sany_validator import validate_string


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
    assert "ParticipantSet == [p \\in Participants |-> p]" in result.fixed_spec
    assert "ASSUME ParticipantSet = =" not in result.fixed_spec
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


def test_fix_tla_syntax_cleans_continued_variable_declarations() -> None:
    spec = """---- MODULE DiningPhilosophers ----
VARIABLES pc, Let, hungry
          forkOwner
    votesReceived  ,\\ Mapping from participant -> boolean indicating YES/NO received,
    decision       ,\\ Final decision by coordinator ("none","committed","aborted"),
    terminated     .\\ Boolean flag whether process has finished
Init ==
   /\\ pc = "idle"
====
"""

    result = fix_tla_syntax(spec)

    assert "cleaned single-line VARIABLES declaration" in result.fixes_applied
    assert "merged continued VARIABLES declaration lines" in result.fixes_applied
    assert "VARIABLES pc, hungry, forkOwner, votesReceived, decision, terminated" in result.fixed_spec
    assert "Let" not in result.fixed_spec
    assert "Mapping from participant" not in result.fixed_spec
    assert '"committed"' not in result.fixed_spec


def test_fix_tla_syntax_normalizes_tex_quantifiers_and_definition_symbol() -> None:
    spec = """---- MODULE DiningPhilosophers ----
VARIABLES pc
THINKING ≜ <<"thinking">>
TypeOK ==
   /\\ \\forall p \\in Procs : pc[p] = THINKING
Next ==
   /\\ \\exists p \\in Procs : pc[p] = THINKING
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized definition symbol to ==" in result.fixes_applied
    assert "normalized lowercase TeX quantifiers" in result.fixes_applied
    assert "THINKING == <<\"thinking\">>" in result.fixed_spec
    assert "\\forall" not in result.fixed_spec
    assert "\\exists" not in result.fixed_spec
    assert "\\A p \\in Procs" in result.fixed_spec
    assert "\\E p \\in Procs" in result.fixed_spec


def test_fix_tla_syntax_cleans_multiline_variable_header() -> None:
    spec = """---- MODULE MutualExclusion ----
VARIABLES
    turn      ,\\ Process whose turn it currently is, flag, process
    flag       ,\\ Flag array indicating each process's intent
Init ==
   /\\ turn = 1
====
"""

    result = fix_tla_syntax(spec)

    assert "cleaned multiline VARIABLES declaration" in result.fixes_applied
    assert "VARIABLES turn, flag" in result.fixed_spec
    assert "process" not in result.fixed_spec
    assert "Flag array indicating" not in result.fixed_spec


def test_fix_tla_syntax_normalizes_unicode_membership_and_temporal_tokens() -> None:
    spec = """---- MODULE DiningPhilosophers ----
VARIABLES pc
Acquire ==
   /\\ \\E i ∊ 1..N : pc[i] = "hungry"
EventualGrant ==
   \\square \\diamond (\\A i ∊ 1..N : pc[i] = "eating")
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized unicode/operator temporal tokens" in result.fixes_applied
    assert "∊" not in result.fixed_spec
    assert "\\square" not in result.fixed_spec
    assert "\\diamond" not in result.fixed_spec
    assert "\\E i \\in 1..N" in result.fixed_spec
    assert "[] <> (\\A i \\in 1..N : pc[i] = \"eating\")" in result.fixed_spec


def test_fix_tla_syntax_removes_parenthesized_empty_unchanged_tuple() -> None:
    spec = """---- MODULE DiningPhilosophers ----
VARIABLES pc
Acquire ==
   /\\ pc = "hungry"
   /\\ UNCHANGED (<<>>)
====
"""

    result = fix_tla_syntax(spec)

    assert "removed UNCHANGED <<>> (empty tuple)" in result.fixes_applied
    assert "UNCHANGED (<<>>)" not in result.fixed_spec


def test_fix_tla_syntax_normalizes_plain_spec_box_next_spacing() -> None:
    spec = """---- MODULE MutualExclusion ----
VARIABLES pc
Init == pc = "idle"
Next == pc' = "idle"
Spec == Init /\\ [] Next
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized plain Spec [] Next spacing" in result.fixes_applied
    assert "Spec == Init /\\ []Next" in result.fixed_spec


def test_fix_tla_syntax_normalizes_quantifier_in_where_and_unchange_tokens() -> None:
    spec = """---- MODULE DiningPhilosophers ----
VARIABLES forkHeldBy
TypeOK ==
    /\\ ALL i IN 1 .. N :
        /\\ NOT \\E p WHERE forkHeldBy[p] = i
Next ==
    /\\ UNCHANGE forkHeldBy'
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized alternate quantifier keywords" in result.fixes_applied
    assert "normalized UNCHANGE operator" in result.fixes_applied
    assert "ALL i IN" not in result.fixed_spec
    assert "WHERE" not in result.fixed_spec
    assert "UNCHANGE forkHeldBy'" not in result.fixed_spec
    assert "\\A i \\in 1 .. N :" in result.fixed_spec
    assert "~ \\E p : forkHeldBy[p] = i" in result.fixed_spec
    assert "UNCHANGED forkHeldBy" in result.fixed_spec


def test_fix_tla_syntax_normalizes_spec_bracket_set_next_form() -> None:
    spec = """---- MODULE MutualExclusion ----
VARIABLES pc, queue, turn
Spec == Init /\\ []_[{pc,queue,turn}](Next)
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized bracket-set Spec temporal formula" in result.fixes_applied
    assert "Spec == Init /\\ [Next]_<<pc, queue, turn>>" in result.fixed_spec


def test_fix_tla_syntax_normalizes_generic_quantifier_in_and_function_constructor_in() -> None:
    spec = """---- MODULE DiningPhilosophers ----
VARIABLES pc, forkOwner
Init ==
   /\\ pc = [j IN 1 .. N |-> "hungry"]
allFree(forkSeq) ==
   \\A f IN forkSeq: ~ \\E p IN 1 .. N: forkOwner[p] = f
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized generic IN quantifiers and constructors" in result.fixes_applied
    assert "[j IN 1 .. N" not in result.fixed_spec
    assert "\\A f IN forkSeq" not in result.fixed_spec
    assert "\\E p IN 1 .. N" not in result.fixed_spec
    assert '[j \\in 1 .. N |-> "hungry"]' in result.fixed_spec
    assert "\\A f \\in forkSeq:" in result.fixed_spec
    assert "\\E p \\in 1 .. N:" in result.fixed_spec


def test_fix_tla_syntax_rewrites_mixed_case_bracketed_unchanged() -> None:
    spec = """---- MODULE MutualExclusion ----
VARIABLES turn
Next ==
   /\\ turn' = turn
   /\\ Unchanged[<<>>]
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote bracketed UNCHANGED form" in result.fixes_applied
    assert "removed UNCHANGED <<>> (empty tuple)" in result.fixes_applied
    assert "Unchanged[" not in result.fixed_spec


def test_fix_tla_syntax_normalizes_double_box_temporal_forms() -> None:
    spec = """---- MODULE KeyValueStore ----
VARIABLES kvs
vars == <<kvs>>
Spec == Init /\\ [][][Next]_vars
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized duplicate temporal box operators" in result.fixes_applied
    assert "[][][Next]_vars" not in result.fixed_spec
    assert "Spec == Init /\\ [][Next]_vars" in result.fixed_spec


def test_fix_tla_syntax_normalizes_backslash_in_case_and_set_comprehension_arrow() -> None:
    spec = """---- MODULE SnapshotIsolation ----
VARIABLES txs
TypeOK ==
    /\\ FORALL k \\In KEYS : k \\IN VALUES
MaxId ==
    MAX({tx.id | tx <- txs} \\cup {1-1})
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized backslash operator casing" in result.fixes_applied
    assert "normalized set-comprehension <- to \\in" in result.fixes_applied
    assert "\\In" not in result.fixed_spec
    assert "\\IN" not in result.fixed_spec
    assert "<-" not in result.fixed_spec
    assert "tx \\in txs" in result.fixed_spec


def test_fix_tla_syntax_normalizes_identifier_question_suffix_and_stray_question_runs() -> None:
    spec = """---- MODULE SnapshotIsolation ----
VARIABLES committed
conflict? ==
    \\E w1, w2 \\in committed : w1 # w2
stale?(k) ==
    ~conflict?
Spec == Init /\\ []<>(vars) \\/ Next)_vars ???
TypeOK ==
    /\\ want = <<TRUE/FALSE>>?
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized identifier question suffixes" in result.fixes_applied
    assert "removed stray question-mark runs" in result.fixes_applied
    assert "conflict?" not in result.fixed_spec
    assert "stale?" not in result.fixed_spec
    assert ">>>?" not in result.fixed_spec
    assert "???" not in result.fixed_spec
    assert "conflict ==" in result.fixed_spec
    assert "stale(k) ==" in result.fixed_spec


def test_fix_tla_syntax_normalizes_bare_quantifier_words_and_boolean_casing() -> None:
    spec = """---- MODULE PubSub ----
VARIABLES topics
Invariant ==
    /\\ forall s in Subscribers:
         exists t in Topics: topics[t] = False
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized bare quantifier words" in result.fixes_applied
    assert "normalized boolean literal casing" in result.fixes_applied
    assert "forall" not in result.fixed_spec
    assert "exists" not in result.fixed_spec
    assert "FALSE" in result.fixed_spec
    assert "\\A s \\in Subscribers:" in result.fixed_spec
    assert "\\E t \\in Topics:" in result.fixed_spec


def test_fix_tla_syntax_normalizes_double_bracket_function_constructor_and_unchanged_case() -> None:
    spec = """---- MODULE DekkersAlgorithm ----
VARIABLES want, turn
Next ==
    /\\ want' = [[w IN {P1,P2}] |-> IF w=P1 THEN TRUE ELSE want[w]]
    /\\ UNCHANGEd turn
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized generic IN quantifiers and constructors" in result.fixes_applied
    assert "normalized double-bracket function constructors" in result.fixes_applied
    assert "normalized UNCHANGED operator casing" in result.fixes_applied
    assert "[[w" not in result.fixed_spec
    assert "UNCHANGEd" not in result.fixed_spec
    assert "[w \\in {P1,P2} |-> IF w=P1 THEN TRUE ELSE want[w]]" in result.fixed_spec
    assert "UNCHANGED turn" in result.fixed_spec


def test_fix_tla_syntax_normalizes_comment_styles_banner_lines_and_logic_words() -> None:
    spec = """---- MODULE FileTransfer ----
*** Type invariant ***
/* Initial state comment */
Init ==
    \\land sent = []
    \\and acked = {}
// fallback branch
Next ==
    \\vee Retry
====
"""

    result = fix_tla_syntax(spec)

    assert "removed markdown-style banner lines" in result.fixes_applied
    assert "normalized non-TLA comment styles" in result.fixes_applied
    assert "normalized logical word operators" in result.fixes_applied
    assert "*** Type invariant ***" not in result.fixed_spec
    assert "/*" not in result.fixed_spec
    assert "*/" not in result.fixed_spec
    assert "//" not in result.fixed_spec
    assert "\\land" not in result.fixed_spec
    assert "\\and" not in result.fixed_spec
    assert "\\vee" not in result.fixed_spec
    assert "(* Initial state comment *)" in result.fixed_spec
    assert "\\* fallback branch" in result.fixed_spec
    assert "/\\ sent = <<>>" in result.fixed_spec
    assert "/\\ acked = {}" in result.fixed_spec
    assert "\\/ Retry" in result.fixed_spec


def test_fix_tla_syntax_rewrites_domain_pipe_in_strips_labels_and_normalizes_terminating_branch() -> None:
    spec = """---- MODULE MutualExclusion ----
VARIABLES procState
ProcessIds == DOMAIN [i |-> i IN 1 .. N]
Init ==
    /\\ LEFT_FORK_INIT: forall f in 1..N: procState[f] = 0
Next ==
    \\/ StepOne
    /\\ Terminating
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote DOMAIN function-constructor membership form" in result.fixes_applied
    assert "removed conjunct labels" in result.fixes_applied
    assert "normalized terminating branch in disjunction block" in result.fixes_applied
    assert "DOMAIN [i \\in 1 .. N |-> i]" in result.fixed_spec
    assert "LEFT_FORK_INIT:" not in result.fixed_spec
    assert "\\A f \\in 1..N: procState[f] = 0" in result.fixed_spec
    assert "    \\/ Terminating" in result.fixed_spec


def test_fix_tla_syntax_rewrites_indented_conjunct_pseudo_definitions() -> None:
    spec = """---- MODULE ReadWriteLock ----
EXTENDS Naturals
CONSTANT MAX_READERS
VARIABLES readers, writerActive

TypeOk ==
    readerCountInRange ==
        (\\E r : (1 <= r) /\\ (r <= MAX_READERS)) \\/ TRUE
    writersAreBoolean == writerActive \\in BOOLEAN
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote indented conjunct pseudo-definitions" in result.fixes_applied
    assert "readerCountInRange ==" not in result.fixed_spec
    assert "writersAreBoolean ==" not in result.fixed_spec
    assert "    /\\ writerActive \\in BOOLEAN" in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="ReadWriteLock")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_normalizes_standalone_at_placeholder_and_variable_prose() -> None:
    spec = """---- MODULE TokenRing ----
EXTENDS Naturals
VARIABLE tpos      (* current owner of the token integer from 1 .. N *), msg, tpos
          NIL means no pending message *)

MsgValues == {"msg", @}

Init ==
    /\\ msg = @
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized standalone @ placeholder to Nil" in result.fixes_applied
    assert "VARIABLE tpos, msg" in result.fixed_spec
    assert 'Nil == "nil"' in result.fixed_spec
    assert 'MsgValues == {"msg", Nil}' in result.fixed_spec
    assert "/\\ msg = Nil" in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="TokenRing")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_collects_orphaned_constant_names_and_constraints() -> None:
    spec = """---- MODULE FileTransfer ----
CONSTANT CHUNK_SIZE, FILE_LENGTH, PACKET_IDS

    (* Maximum number of retries for each chunk *)
    MAX_RETRY >= 1,

    (* Set of all possible packet identifiers *)
    PACKET_IDS : SUBSET Nat,
VARIABLES sentChunks
====
"""

    result = fix_tla_syntax(spec)

    assert "merged orphaned constant annotations" in result.fixes_applied
    assert "normalized orphaned constant constraints to ASSUME" in result.fixes_applied
    assert "CONSTANT CHUNK_SIZE, FILE_LENGTH, PACKET_IDS, MAX_RETRY" in result.fixed_spec
    assert "ASSUME MAX_RETRY >= 1" in result.fixed_spec
    assert "ASSUME PACKET_IDS \\in SUBSET Nat" in result.fixed_spec


def test_fix_tla_syntax_collects_bare_orphaned_constant_names() -> None:
    spec = """---- MODULE GCounter ----
CONSTANT NodeSet
 MaxVal    \\ Upper bound for any individual increment per step
VARIABLES counts
====
"""

    result = fix_tla_syntax(spec)

    assert "merged orphaned constant annotations" in result.fixes_applied
    assert "CONSTANT NodeSet, MaxVal" in result.fixed_spec
    assert "Upper bound for any individual increment per step" not in result.fixed_spec


def test_fix_tla_syntax_collects_orphaned_constants_after_top_level_comment() -> None:
    spec = """---- MODULE MemoryAllocator ----
CONSTANT N, Client
\\* Enumerate all possible client identifiers; for simplicity we bound it by M
M           \\ Maximum number of distinct clients
ASSUME N >= 1
====
"""

    result = fix_tla_syntax(spec)

    assert "merged orphaned constant annotations" in result.fixes_applied
    assert "CONSTANT N, Client, M" in result.fixed_spec
    assert "\\* Enumerate all possible client identifiers" not in result.fixed_spec


def test_fix_tla_syntax_normalizes_bare_quantifiers_with_backslash_in_and_doubled_conjunctions() -> None:
    spec = """---- MODULE FileTransfer ----
TypeOK ==
           /\\ forall p \\in PACKET_IDS:
                retryCount[p] \\in 0..MAX_RETRY
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized bare quantifier words" in result.fixes_applied
    assert "\\A p \\in PACKET_IDS:" in result.fixed_spec


def test_fix_tla_syntax_normalizes_colon_membership_from_disjunctive_and_doubled_backslash_lines() -> None:
    spec = """---- MODULE Broker ----
TypeOk ==
    \\/ subs : [Topic |-> SUBSET(SubIds)]
       /\\\\ msgSeqs : [Topic |-> Seq(Message)]
       /\\\\ delivered : [SubscriberId -> BOOLEAN]
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized colon membership conjuncts" in result.fixes_applied
    assert "\\/ subs :" not in result.fixed_spec
    assert "/\\\\ msgSeqs :" not in result.fixed_spec
    assert "/\\\\ delivered :" not in result.fixed_spec
    assert "/\\ subs \\in [Topic |-> SUBSET(SubIds)]" in result.fixed_spec
    assert "/\\ msgSeqs \\in [Topic |-> Seq(Message)]" in result.fixed_spec
    assert "/\\ delivered \\in [SubscriberId -> BOOLEAN]" in result.fixed_spec


def test_fix_tla_syntax_normalizes_function_set_arrow_notation() -> None:
    spec = """---- MODULE DistributedSnapshot ----
TypeInvariant ==
    /\\ procState \\in P -> {"unrecorded","recorder"}
    /\\ chanMsg \\in (OutChannels x InChannels) -> Sequence[Message]
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized function-set arrow notation" in result.fixes_applied
    assert '/\\ procState \\in [P -> {"unrecorded","recorder"}]' in result.fixed_spec
    assert '/\\ chanMsg \\in [(OutChannels \\X InChannels) -> Seq(Message)]' in result.fixed_spec


def test_fix_tla_syntax_normalizes_subseteq_function_set_arrow_notation() -> None:
    spec = """---- MODULE SingleDecreePaxos ----
TypeOK ==
    /\\ pBallots \\subseteq PROPOSER_IDS --> BALLOT_NUMBERS
    /\\ accPromises \\subseteq ACCEPTOR_IDS --> (BALLOT_NUMBERS --> BOOLEAN)
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized function-set arrow notation" in result.fixes_applied
    assert '/\\ pBallots \\in [PROPOSER_IDS -> BALLOT_NUMBERS]' in result.fixed_spec
    assert '/\\ accPromises \\in [ACCEPTOR_IDS -> [BALLOT_NUMBERS -> BOOLEAN]]' in result.fixed_spec


def test_fix_tla_syntax_removes_orphan_variable_annotation_lines() -> None:
    spec = """---- MODULE SingleDecreePaxos ----
VARIABLES pBallots, accAcks, accPromises, pValues, proposer

    accPromises   ,  (* map[acceptorId] : [ballot |-> {maxPromised} ]*)
    accAcks        ,  (* map[accid][proposalNumber]->{value,votedByMaxB} *)

TypeOK == TRUE
====
"""

    result = fix_tla_syntax(spec)

    assert "removed orphan variable annotation lines" in result.fixes_applied
    assert "accPromises   ,  (*" not in result.fixed_spec
    assert "accAcks        ,  (*" not in result.fixed_spec


def test_fix_tla_syntax_normalizes_bare_star_comments_and_guarded_disjuncts() -> None:
    spec = """---- MODULE TokenRing ----
Next ==
        \\/ (tpos < N) =>
            /\\ tpos' = tpos + 1
               * If there was an outgoing message it stays until delivered.
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized bare star comment lines" in result.fixes_applied
    assert "normalized guarded disjunct lines" in result.fixes_applied
    assert "\\/ (tpos < N) =>" not in result.fixed_spec
    assert " * If there was an outgoing message" not in result.fixed_spec
    assert "\\/ /\\ (tpos < N)" in result.fixed_spec
    assert "\\* If there was an outgoing message it stays until delivered." in result.fixed_spec


def test_fix_tla_syntax_indents_root_level_operator_conjunctions() -> None:
    spec = """---- MODULE FileTransfer ----
Init ==
(* comment *)
/\\ sentChunks = []
/\\ ackedPackets = {}

Next ==
\\/
/\\ currentChunkIndex < FILE_LENGTH
/\\ SendPacket(currentChunkIndex+1)
====
"""

    result = fix_tla_syntax(spec)

    assert "indented root-level operator conjunctions/disjunctions" in result.fixes_applied
    assert "Init ==\n(* comment *)\n    /\\ sentChunks = <<>>" in result.fixed_spec
    assert "\nNext ==\n    \\/ /\\ currentChunkIndex < FILE_LENGTH" in result.fixed_spec
    assert "\n       /\\ SendPacket(currentChunkIndex+1)" in result.fixed_spec


def test_fix_tla_syntax_rewrites_empty_bracket_sequence_literals() -> None:
    spec = """---- MODULE FileTransfer ----
Init ==
    /\\ sentChunks = []
    /\\ channelBuffer = []
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote [] sequence literals to <<>>" in result.fixes_applied
    assert "/\\ sentChunks = <<>>" in result.fixed_spec
    assert "/\\ channelBuffer = <<>>" in result.fixed_spec


def test_fix_tla_syntax_normalizes_cartesian_product_and_sequence_type_notation() -> None:
    spec = """---- MODULE DistributedSnapshot ----
TypeInvariant ==
    /\\ chanMsg \\in [(OutChannels x InChannels) -> Sequence[Message]]
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized cartesian product notation" in result.fixes_applied
    assert "normalized Sequence[...] type notation" in result.fixes_applied
    assert "\\in [(OutChannels \\X InChannels) -> Seq(Message)]" in result.fixed_spec


def test_fix_tla_syntax_normalizes_elseif_tokenization() -> None:
    spec = """---- MODULE DistributedSnapshot ----
NextProc(p) ==
    IF procState[p] = "unrecorded" THEN
        procState
    ELSEIF procState[p] = "recorder" THEN
        recorder
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized ELSEIF tokenization" in result.fixes_applied
    assert "ELSEIF" not in result.fixed_spec
    assert "ELSE IF procState[p] = \"recorder\" THEN" in result.fixed_spec


def test_fix_tla_syntax_normalizes_word_and_or_operators() -> None:
    spec = """---- MODULE DistributedSnapshot ----
NextProc(p) ==
    IF procState[p] = "recorder" AND recorder = NULL THEN
        recorder
    ELSE IF procState[p] = "other" OR recorder = p THEN
        procState
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized word AND/OR operators" in result.fixes_applied
    assert " AND " not in result.fixed_spec
    assert " OR " not in result.fixed_spec
    assert 'IF procState[p] = "recorder" /\\ recorder = NULL THEN' in result.fixed_spec
    assert 'ELSE IF procState[p] = "other" \\/ recorder = p THEN' in result.fixed_spec


def test_fix_tla_syntax_normalizes_curried_style_operator_calls() -> None:
    spec = """---- MODULE QueueOps ----
ConsumerAction ==
    /\\ q' = RemoveAt(head - 1)(q)
    /\\ channelBuffer' = RemoveFirstWhere(\\x: x[1] = p)(channelBuffer)
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized curried-style operator calls" in result.fixes_applied
    assert "RemoveAt(head - 1)(q)" not in result.fixed_spec
    assert "RemoveFirstWhere(\\x: x[1] = p)(channelBuffer)" not in result.fixed_spec
    assert "rewrote remove-front sequence helpers as Tail" in result.fixes_applied
    assert "RemoveAt(head - 1, q)" not in result.fixed_spec
    assert "Tail(q)" in result.fixed_spec
    assert "rewrote backslash lambda predicates as LAMBDA" in result.fixes_applied
    assert "RemoveFirstWhere(LAMBDA x : x[1] = p, channelBuffer)" in result.fixed_spec


def test_fix_tla_syntax_normalizes_sequence_helper_aliases() -> None:
    spec = """---- MODULE BoundedFIFO ----
EXTENDS Sequences
VARIABLES q, size

ProducerAction(item) ==
    /\\ q' = Append(SeqSubseq(q, 1..size), SeqFromList([item]))
ConsumerAction ==
    LET oldHeadVal == SubSequence(q, 1, size) IN
        /\\ q' = oldHeadVal
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized sequence helper aliases" in result.fixes_applied
    assert "SeqSubseq" not in result.fixed_spec
    assert "SeqFromList" not in result.fixed_spec
    assert "SubSequence" not in result.fixed_spec
    assert "Append(SubSeq(q, 1, size), <<item>>)" in result.fixed_spec
    assert "LET oldHeadVal == SubSeq(q, 1, size) IN" in result.fixed_spec


def test_fix_tla_syntax_removes_primes_from_operator_parameters() -> None:
    spec = """---- MODULE QueueOps ----
EXTENDS Sequences
VARIABLES q

ProducerAction(item) ==
    /\\ item' \\in q
    /\\ q' = Append(q, item)
====
"""

    result = fix_tla_syntax(spec)

    assert "removed primes from operator parameters" in result.fixes_applied
    assert "item' \\in q" not in result.fixed_spec
    assert "/\\ item \\in q" in result.fixed_spec


def test_fix_tla_syntax_removes_shadowed_variable_names_from_declaration() -> None:
    spec = """---- MODULE BoundedFIFO ----
EXTENDS Sequences
VARIABLE q, head, item, q, size, tail

vars == <<q, head, tail, size>>

ProducerAction(item) ==
    /\\ q' = Append(q, item)
====
"""

    result = fix_tla_syntax(spec)

    assert "removed shadowed variable names from declaration" in result.fixes_applied
    assert "VARIABLE q, head, tail, size" in result.fixed_spec
    assert "VARIABLE q, head, item, size, tail" not in result.fixed_spec
    assert "vars == <<q, head, tail, size>>" in result.fixed_spec


def test_fix_tla_syntax_rewrites_backslash_lambda_predicates() -> None:
    spec = """---- MODULE QueueOps ----
ConsumerAction ==
    /\\ channelBuffer' = RemoveFirstWhere(\\x: x[1] = p, channelBuffer)
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote backslash lambda predicates as LAMBDA" in result.fixes_applied
    assert "RemoveFirstWhere(\\x: x[1] = p, channelBuffer)" not in result.fixed_spec
    assert "RemoveFirstWhere(LAMBDA x : x[1] = p, channelBuffer)" in result.fixed_spec


def test_fix_tla_syntax_normalizes_multiline_spec_temporal_formula_with_stray_backslash() -> None:
    spec = """---- MODULE BoundedFIFO ----
Spec == Init /\\
        [][ Next ]_vars \\
        /\\ TypeOk
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized multiline Spec temporal formula" in result.fixes_applied
    assert "[][ Next ]_vars \\" not in result.fixed_spec
    assert "Spec == Init /\\ [][Next]_vars /\\ TypeOk" in result.fixed_spec


def test_fix_tla_syntax_normalizes_zero_arg_operator_defs_and_calls() -> None:
    spec = """---- MODULE RaftLeaderElection ----
LeaderCommit ==
    /\\ majorityVotesReceived()
majorityVotesReceived() ==
    TRUE
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized zero-arg operator definitions/calls" in result.fixes_applied
    assert "majorityVotesReceived() ==" not in result.fixed_spec
    assert "/\\ majorityVotesReceived" in result.fixed_spec
    assert "majorityVotesReceived ==" in result.fixed_spec


def test_fix_tla_syntax_inserts_missing_record_type_commas() -> None:
    spec = """---- MODULE RaftLeaderElection ----
CANDIDATE_MSG == [id: ServerSet term: Int]
====
"""

    result = fix_tla_syntax(spec)

    assert "inserted missing record field commas" in result.fixes_applied
    assert "CANDIDATE_MSG == [id: ServerSet, term: Int]" in result.fixed_spec


def test_fix_tla_syntax_removes_dangling_else_if_after_let_in_action() -> None:
    spec = """---- MODULE RaftLeaderElection ----
VoteRequest(cand) ==
    LET newTerm == cand.term IN
            /\\ currentTerm' = newTerm
            /\\ votedFor' = cand.id
        ELSE IF newTerm < currentTerm THEN
            /\\ UNCHANGED vars
Next == TRUE
====
"""

    result = fix_tla_syntax(spec)

    assert "removed dangling ELSE IF after LET-IN action" in result.fixes_applied
    assert "ELSE IF newTerm < currentTerm THEN" not in result.fixed_spec


def test_fix_tla_syntax_normalizes_len_broken_in_and_escaped_comment() -> None:
    spec = """---- MODULE ClockSync ----
TypeInvariant ==
    /\\ len(offsets) = NumNodes
    /\\ (\\A j \\i n DOMAIN clocks : clocks[j] >= 0)

(\\* All variables must be finite sets.\\*)
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized Len(...) casing" in result.fixes_applied
    assert "normalized broken \\i n token" in result.fixes_applied
    assert "normalized escaped TLA comments" in result.fixes_applied
    assert "len(offsets)" not in result.fixed_spec
    assert "\\i n" not in result.fixed_spec
    assert "(\\*" not in result.fixed_spec
    assert "Len(offsets)" in result.fixed_spec
    assert "\\A j \\in DOMAIN clocks" in result.fixed_spec
    assert "(* All variables must be finite sets. *)" in result.fixed_spec


def test_fix_tla_syntax_normalizes_uppercase_len_casing() -> None:
    spec = """---- MODULE FileTransfer ----
SendPacket(p) ==
    /\\ p > LEN(channelBuffer)
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized Len(...) casing" in result.fixes_applied
    assert "LEN(channelBuffer)" not in result.fixed_spec
    assert "Len(channelBuffer)" in result.fixed_spec


def test_fix_tla_syntax_rewrites_chained_inequalities() -> None:
    spec = """---- MODULE ClockSync ----
TypeInvariant ==
    /\\ (\\A i \\in DOMAIN offsets : -MaxOffset <= offsets[i] <= MaxOffset)
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote chained inequalities" in result.fixes_applied
    assert "(-MaxOffset <= offsets[i]) /\\ (offsets[i] <= MaxOffset)" in result.fixed_spec


def test_fix_tla_syntax_rewrites_chained_inequalities_with_literal_bounds() -> None:
    spec = """---- MODULE ReadWriteLock ----
TypeOk ==
    /\\ (\\E r : 1 <= r <= MAX_READERS) \\/ TRUE
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote chained inequalities" in result.fixes_applied
    assert "(1 <= r) /\\ (r <= MAX_READERS)" in result.fixed_spec


def test_fix_tla_syntax_rewrites_nested_function_initializer_zero_body() -> None:
    spec = """---- MODULE ClockSync ----
Init ==
    /\\ offsets = [k \\in [1..NumNodes | -> 0]]
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote nested function initializer body" in result.fixes_applied
    assert "[k \\in [1..NumNodes | -> 0]]" not in result.fixed_spec
    assert "[k \\in 1..NumNodes |-> 0]" in result.fixed_spec


def test_fix_tla_syntax_removes_dangling_let_action_fragment_before_spec() -> None:
    spec = """---- MODULE Peterson ----
Next ==
    \\/ Process(1)
    \\/ Process(2)

    LET j \\be i # 1 + 1 IN

      /\\ flags[i] \\in = TRUE
         /\\ turn' := j
         /\\ UNCHANGED <<flags[j]>>

Spec == Init /\\ [][Next]_<<flags, turn>>
====
"""

    result = fix_tla_syntax(spec)

    assert "removed dangling LET action fragment before Spec" in result.fixes_applied
    assert "LET j \\be i # 1 + 1 IN" not in result.fixed_spec
    assert "turn' := j" not in result.fixed_spec
    assert "Spec == Init /\\ [][Next]_<<flags, turn>>" in result.fixed_spec


def test_fix_tla_syntax_fills_empty_next_after_dangling_fragment_cleanup() -> None:
    spec = """---- MODULE ReadWriteLock ----
VARIABLES readers, writerActive
vars == <<readers, writerActive>>
Init ==
    /\\ readers = 0
    /\\ writerActive = FALSE

Next ==
    LET nextReaders == IF writerActive THEN readers ELSE readers' IN
    CASE

Spec == Init /\\ [][Next]_vars
====
"""

    result = fix_tla_syntax(spec)

    assert "removed dangling LET action fragment before Spec" in result.fixes_applied
    assert "filled empty Next with UNCHANGED vars" in result.fixes_applied
    assert "Next == /\\ UNCHANGED vars" in result.fixed_spec


def test_fix_tla_syntax_preserves_valid_let_action_before_later_definitions() -> None:
    spec = """---- MODULE Queue ----
VARIABLES tail, size

ProducerAction(item) ==
    LET newTail == IF tail # 3 THEN tail + 1 ELSE 1 IN
        /\\ size < 3
        /\\ tail' = newTail

Next ==
    ProducerAction(1)

Spec == Init /\\ [][Next]_<<tail, size>>
====
"""

    result = fix_tla_syntax(spec)

    assert "removed dangling LET action fragment before Spec" not in result.fixes_applied
    assert "LET newTail == IF tail # 3 THEN tail + 1 ELSE 1 IN" in result.fixed_spec
    assert "/\\ tail' = newTail" in result.fixed_spec
    assert "Next ==" in result.fixed_spec


def test_fix_tla_syntax_normalizes_inline_double_dash_comment() -> None:
    spec = """---- MODULE ReadWriteLock ----
TypeOk ==
    /\\ TRUE  -- placeholder for range check
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized inline double-dash comments" in result.fixes_applied
    assert "-- placeholder for range check" not in result.fixed_spec
    assert "\\* placeholder for range check" in result.fixed_spec


def test_fix_tla_syntax_normalizes_inline_double_dash_comment_on_continuation_line() -> None:
    spec = """---- MODULE ReadWriteLock ----
TypeOk ==
    /\\
        (\\E r : (1 <= r) /\\ (r <= MAX_READERS)) \\/ TRUE  -- placeholder for range check
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized inline double-dash comments" in result.fixes_applied
    assert "-- placeholder for range check" not in result.fixed_spec
    assert "\\* placeholder for range check" in result.fixed_spec


def test_fix_tla_syntax_normalizes_inline_double_dash_comment_after_pseudo_definition_rewrite() -> None:
    spec = """---- MODULE ReadWriteLock ----
TypeOk ==
    readerCountInRange ==
        (\\E r : (1 <= r) /\\ (r <= MAX_READERS)) \\/ TRUE  -- placeholder for range check
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote indented conjunct pseudo-definitions" in result.fixes_applied
    assert "normalized inline double-dash comments" in result.fixes_applied
    assert "-- placeholder for range check" not in result.fixed_spec
    assert "\\* placeholder for range check" in result.fixed_spec


def test_fix_tla_syntax_does_not_corrupt_module_header_or_block_comment_lines() -> None:
    spec = """---- MODULE ReadWriteLock ----
(* ------------------------------------------------------------------ *)
TypeOk ==
    readerCountInRange ==
        (\\E r : (1 <= r) /\\ (r <= MAX_READERS)) \\/ TRUE  -- placeholder for range check
====
"""

    result = fix_tla_syntax(spec)

    assert "---- MODULE ReadWriteLock ----" in result.fixed_spec
    assert "(* ------------------------------------------------------------------ *)" in result.fixed_spec


def test_fix_tla_syntax_rewrites_multiline_function_initializer_missing_arrow() -> None:
    spec = """---- MODULE ClockSync ----
StepDrift ==
    LET newOffsets == [n \\in 1..NumNodes |

                            offsets[n] + RandomChoice(-MaxOffset .. +MaxOffset)

                           offsets[n]]
     IN
        /\\ offsets' = newOffsets
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote multiline function initializer missing |->" in result.fixes_applied
    assert "normalized signed upper bounds in ranges" in result.fixes_applied
    assert "[n \\in 1..NumNodes |-> offsets[n] + RandomChoice(-MaxOffset .. MaxOffset)]" in result.fixed_spec


def test_fix_tla_syntax_rewrites_malformed_delta_set_as_function_initializer() -> None:
    spec = """---- MODULE ClockSync ----
SyncRound ==
    LET delta == { c \\in DOMAIN clocks :

                          Sign(avgClock - clocks[c])

                         0 }
        updatedClks == [i \\in DOMAIN clocks |-> clocks[i]+delta(i)]
    IN
        /\\ clocks' = updatedClks
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote malformed delta set as function initializer" in result.fixes_applied
    assert "delta == [c \\in DOMAIN clocks |-> Sign(avgClock - clocks[c])]" in result.fixed_spec


def test_fix_tla_syntax_normalizes_sum_set_aggregate_notation() -> None:
    spec = """---- MODULE ClockSync ----
Avg ==
    (SUM_{c \\in DOMAIN clocks} clocks[c]) \\div Len(DOMAIN clocks)

Total ==
    SUM_{n \\in NodeSet}(MAX({counts[n][m] : m \\in NodeSet}))
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized SUM_{x in S} aggregate notation" in result.fixes_applied
    assert "(Sum([c \\in DOMAIN clocks |-> clocks[c]])) \\div Len(DOMAIN clocks)" in result.fixed_spec
    assert "Sum([n \\in NodeSet |-> MAX({counts[n][m] : m \\in NodeSet})])" not in result.fixed_spec
    assert "Sum([n \\in NodeSet |-> MAX({counts[n][m] : m \\in NodeSet}]))" in result.fixed_spec


def test_fix_tla_syntax_expands_counts_column_max_shorthand() -> None:
    spec = """---- MODULE GCounter ----
GlobalCount ==
    Sum([n \\in NodeSet |-> MAX(\\{counts[][n]\\}]))
====
"""

    result = fix_tla_syntax(spec)

    assert "expanded counts[][n] max shorthand" in result.fixes_applied
    assert "Sum([n \\in NodeSet |-> Max({counts[m][n] : m \\in NodeSet})])" in result.fixed_spec


def test_fix_tla_syntax_removes_malformed_unchanged_at_invariant_line() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
TypeOK ==
    /\\ phase \\in {"init", "prepare", "commit", "abort"}
    /\\ UNCHANGED @votes[*] \\/ (\\A v : Votes[v]) #v = NONE => FALSE
====
"""

    result = fix_tla_syntax(spec)

    assert "removed malformed UNCHANGED @ invariant line" in result.fixes_applied
    assert "UNCHANGED @votes[*]" not in result.fixed_spec


def test_fix_tla_syntax_rewrites_record_set_and_single_angle_tuple_forms() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
TypeOK ==
    /\\ messages \\subseteq [{ sender: ANY,
                              receiver: ANY,
                              kind: MessageTypes }]

Init ==
    /\\ messages =
        {<"Coordinator", p, "Prepare"> | p \\in Participants}

sendMsg(s,r,m) == < s , r , m >
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote bracketed record-set syntax" in result.fixes_applied
    assert "rewrote single-angle tuple syntax" in result.fixes_applied
    assert "[sender: ANY, receiver: ANY, kind: MessageTypes]" in result.fixed_spec
    assert '{<<"Coordinator", p, "Prepare">> : p \\in Participants}' in result.fixed_spec
    assert "sendMsg(s,r,m) == <<s , r , m >>" in result.fixed_spec


def test_fix_tla_syntax_inserts_missing_function_constructor_arrow() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
UpdateMsgs ==
    /\\ msgs' = [msgKind IN MessageTypes |
                  IF msgKind = "VoteYes" \\/ msgKind = "VoteNo" THEN TRUE ELSE FALSE]
====
"""

    result = fix_tla_syntax(spec)

    assert "inserted missing function constructor |->" in result.fixes_applied
    assert "[msgKind \\in MessageTypes |->" in result.fixed_spec


def test_fix_tla_syntax_rewrites_malformed_vote_message_function_update() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
CONSTANT Participants

UpdateMsgs(msg) ==
    /\\ msgs' = [msgKind IN MessageTypes |
                  (IF msgKind = "VoteYes" \\/ msgKind="VoteNo") =>
                      IF \\E x \\in participants :
                         ((x,msgKind)=msg)
                      THEN [msgs EXCEPT ![msgKind]=TRUE]]
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote malformed vote message function update" in result.fixes_applied
    assert "normalized lowercase constant aliases" in result.fixes_applied
    assert "=>" not in result.fixed_spec
    assert "[msgs EXCEPT ![msgKind]=TRUE]" not in result.fixed_spec
    assert '[msgKind \\in MessageTypes |-> IF (msgKind = "VoteYes" \\/ msgKind="VoteNo") /\\ (\\E x \\in Participants : <<x, "Coordinator", msgKind>> = msg) THEN TRUE ELSE FALSE]' in result.fixed_spec


def test_fix_tla_syntax_normalizes_malformed_slash_double_backslash_action_line() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
deliver(msg) ==
    /\\\\ UNCHANGED <<phase, votes>>
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized malformed backslash-leading action lines" in result.fixes_applied
    assert "/\\\\ UNCHANGED" not in result.fixed_spec
    assert "/\\ UNCHANGED <<phase, votes>>" in result.fixed_spec


def test_fix_tla_syntax_rewrites_disjoined_if_branch_as_else_if() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
deliver(msg) ==
    /\\ IF msg.receiver = "Coordinator" THEN
          CASE msg.sender \\in Participants ->
              /\\ msgs' = msgs
              /\\ UNCHANGED <<phase, votes>>
           [] TRUE -> UNCHANGED <<phase, votes>>
       \\/ IF msg.receiver \\in Participants THEN
              /\\ phase' = phase
              /\\ votes' = votes
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote disjoined IF branch as ELSE IF" in result.fixes_applied
    assert "\\/ IF msg.receiver \\in Participants THEN" not in result.fixed_spec
    assert "ELSE IF msg.receiver \\in Participants THEN" in result.fixed_spec


def test_fix_tla_syntax_completes_disjoined_if_else_if_chain() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
CONSTANT Participants
VARIABLES phase, votes, msgs

deliver(msg) ==
    /\\ IF msg.receiver = "Coordinator" THEN
          CASE msg.sender \\in Participants ->
              /\\ msgs' = msgs
              /\\ UNCHANGED <<phase, votes>>
           [] TRUE -> UNCHANGED <<phase, votes>>
       \\/ IF msg.receiver \\in Participants THEN
              /\\ phase' = phase
              /\\ votes' = votes
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote disjoined IF branch as ELSE IF" in result.fixes_applied
    assert "completed disjoined IF/ELSE IF chain missing final ELSE" in result.fixes_applied
    assert "ELSE IF msg.receiver \\in Participants THEN" in result.fixed_spec
    assert "ELSE TRUE" in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="TwoPhaseCommit")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_replaces_malformed_let_in_placeholder_tail_with_true() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
EXTENDS Naturals
CONSTANT Participants
VARIABLES votes

Next ==
    LET sendMsg(s, r, m) == <<s, r, m>>
    in
      /\\ (\\E p : p \\in Participants & NOT p \\in DOMAIN(votes))
      /\\ messageToSend? := {<p, "Coordinator", "Prepare"> | ...}   \\* placeholder for sending vote requests?
====
"""

    result = fix_tla_syntax(spec)

    assert "replaced malformed LET-IN placeholder tail with IN TRUE" in result.fixes_applied
    assert "messageToSend" not in result.fixed_spec
    assert "placeholder for sending vote requests" not in result.fixed_spec
    assert "IN TRUE" in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="TwoPhaseCommit")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_normalizes_msgs_alias_to_messages_when_msgs_is_undeclared() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
VARIABLES messages

UpdateMsgs ==
    /\\ msgs' = [msgKind \\in {"VoteYes"} |-> TRUE]
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized msgs alias to messages" in result.fixes_applied
    assert "msgs'" not in result.fixed_spec
    assert "messages' = [msgKind \\in {\"VoteYes\"} |-> TRUE]" in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="TwoPhaseCommit")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_rewrites_message_record_any_fields_to_actor_domain() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
CONSTANT Participants
VARIABLES messages

MessageTypes == {"Prepare", "VoteYes", "VoteNo", "Commit", "Abort"}

TypeOK ==
    /\\ messages \\subseteq [{ sender: ANY,
                              receiver: ANY,
                              kind: MessageTypes }]

Init ==
    /\\ messages = {<<"Coordinator", p, "Prepare">> : p \\in Participants}
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote ANY message record fields to actor domain" in result.fixes_applied
    assert "[sender: ANY, receiver: ANY, kind: MessageTypes]" not in result.fixed_spec
    assert '[sender: Participants \\cup {"Coordinator"}, receiver: Participants \\cup {"Coordinator"}, kind: MessageTypes]' in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="TwoPhaseCommit")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_adds_sequences_extend_when_len_is_used() -> None:
    spec = """---- MODULE ClockSync ----
EXTENDS Naturals, FiniteSets, Integers
CONSTANT NumNodes
VARIABLES offsets

TypeInvariant ==
    /\\ Len(offsets) = NumNodes
====
"""

    result = fix_tla_syntax(spec)

    assert "added Sequences to EXTENDS for Len" in result.fixes_applied
    assert "EXTENDS Naturals, FiniteSets, Integers, Sequences" in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="ClockSync")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_rewrites_zero_arg_function_value_call_to_indexing() -> None:
    spec = """---- MODULE ClockSync ----
SyncRound ==
    LET delta == [c \\in DOMAIN clocks |-> Sign(avgClock - clocks[c])]
        updatedClks == [i \\in DOMAIN clocks |-> clocks[i] + delta(i)]
    IN
        /\\ clocks' = updatedClks
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote zero-arg function-value calls as indexing" in result.fixes_applied
    assert "delta(i)" not in result.fixed_spec
    assert "delta[i]" in result.fixed_spec


def test_fix_tla_syntax_moves_forward_action_defs_before_next() -> None:
    spec = """---- MODULE ClockSync ----
EXTENDS Naturals
VARIABLES clocks, offsets
vars == <<clocks, offsets>>

Init == /\\ clocks = 0 /\\ offsets = 0

Next ==
    \\/ StepDrift
    \\/ Terminating

StepDrift ==
    /\\ clocks' = clocks
    /\\ offsets' = offsets

Terminating ==
    /\\ UNCHANGED vars
====
"""

    result = fix_tla_syntax(spec)

    assert "moved forward action definitions before Next" in result.fixes_applied
    assert result.fixed_spec.index("StepDrift ==") < result.fixed_spec.index("Next ==")
    assert result.fixed_spec.index("Terminating ==") < result.fixed_spec.index("Next ==")
    sany_result = validate_string(result.fixed_spec, module_name="ClockSync")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_auto_defines_randomchoice_sum_and_sign_helpers() -> None:
    spec = """---- MODULE ClockSync ----
EXTENDS Naturals, Integers, Sequences
CONSTANT NumNodes, MaxOffset
VARIABLES clocks, offsets
vars == <<clocks, offsets>>

Init ==
    /\\ clocks = [j \\in 1..NumNodes |-> 0]
    /\\ offsets = [k \\in 1..NumNodes |-> 0]

StepDrift ==
    LET newOffsets == [n \\in 1..NumNodes |-> offsets[n] + RandomChoice(-MaxOffset .. MaxOffset)]
    IN
        /\\ offsets' = newOffsets
        /\\ UNCHANGED clocks

SyncRound ==
    LET avgClock == (Sum([c \\in DOMAIN clocks |-> clocks[c]])) \\div Len(DOMAIN clocks)
        delta == [c \\in DOMAIN clocks |-> Sign(avgClock - clocks[c])]
        updatedClks == [i \\in DOMAIN clocks |-> clocks[i] + delta[i]]
    IN
        /\\ clocks' = updatedClks
        /\\ UNCHANGED offsets

Next == \\/ StepDrift \\/ SyncRound
Spec == Init /\\ [][Next]_vars
====
"""

    result = fix_tla_syntax(spec)

    assert "auto-defined RandomChoice helper" in result.fixes_applied
    assert "auto-defined Sum helper" in result.fixes_applied
    assert "auto-defined Sign helper" in result.fixes_applied
    assert "RandomChoice(S) == CHOOSE x \\in S : TRUE" in result.fixed_spec
    assert "Sign(x) == IF x > 0 THEN 1 ELSE IF x < 0 THEN -1 ELSE 0" in result.fixed_spec
    assert "Sum(S) ==" in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="ClockSync")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_normalizes_diamond_next_spec_to_boxed_next_vars() -> None:
    spec = """---- MODULE ClockSync ----
VARIABLES clocks, offsets
vars == <<clocks, offsets>>

Init == /\\ clocks = 0 /\\ offsets = 0
Next == /\\ clocks' = clocks /\\ offsets' = offsets
Spec == Init /\\ []<>(Next)
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized malformed diamond Next Spec formula" in result.fixes_applied
    assert "Spec == Init /\\ [][Next]_vars" in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="ClockSync")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_completes_conjunctive_if_block_missing_else() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
deliver(msg) ==
    /\\ IF msg.kind = "Commit" THEN
           /\\ UNCHANGED <<votes, messages>>
       /\\ phase' = phase
====
"""

    result = fix_tla_syntax(spec)

    assert "completed conjunctive IF block missing ELSE branch" in result.fixes_applied
    assert "ELSE TRUE" in result.fixed_spec
    assert result.fixed_spec.index("ELSE TRUE") < result.fixed_spec.index("/\\ phase' = phase")


def test_fix_tla_syntax_rewrites_malformed_union_singleton_update() -> None:
    spec = """---- MODULE TwoPhaseCommit ----
deliver(msg) ==
    /\\ messages'=UNION(messages,\\{sendMsg(msg.receiver,"Coordinator","Ack"\\})\\}
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote malformed UNION singleton update" in result.fixes_applied
    assert 'UNION(messages,\\{sendMsg(msg.receiver,"Coordinator","Ack"\\})\\}' not in result.fixed_spec
    assert 'messages\' = messages \\cup {sendMsg(msg.receiver, "Coordinator", "Ack")}' in result.fixed_spec


def test_fix_tla_syntax_groups_mixed_guard_block_and_promotes_updates() -> None:
    spec = """---- MODULE FileTransfer ----
SendPacket(p) ==
    /\\ ~(p \\in sentChunks)
    \\/ p > LEN(channelBuffer)
    /\\
channelBuffer' = Append(channelBuffer, <<p>>)
retryCount'[p] = MAX_RETRY
====
"""

    result = fix_tla_syntax(spec)

    assert "grouped mixed disjunct guard into conjunction block" in result.fixes_applied
    assert "promoted dangling update lines into conjunction block" in result.fixes_applied
    assert "/\\ (~(p \\in sentChunks) \\/ p > Len(channelBuffer))" in result.fixed_spec
    assert "/\\ channelBuffer' = Append(channelBuffer, <<p>>)" in result.fixed_spec
    assert "/\\ retryCount' = [retryCount EXCEPT ![p] = MAX_RETRY]" in result.fixed_spec


def test_fix_tla_syntax_rewrites_unless_skip_else_block_to_if_unchanged_else() -> None:
    spec = """---- MODULE FileTransfer ----
VARIABLES sentChunks, ackedPackets, channelBuffer, currentChunkIndex, retryCount

AckReceived(p) ==
UNLESS p \\# IN CHANNEL_BUFFER then skip else (
    /\\ ackedPackets' = ackedPackets \\cup {p}
    /\\ channelBuffer' = channelBuffer
)
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote UNLESS skip/else pseudocode as IF/UNCHANGED/ELSE" in result.fixes_applied
    assert "UNLESS p \\# IN CHANNEL_BUFFER then skip else" not in result.fixed_spec
    assert (
        "IF ~(p \\in channelBuffer) THEN UNCHANGED <<sentChunks, ackedPackets, channelBuffer, currentChunkIndex, retryCount>> ELSE ("
        in result.fixed_spec
    )


def test_fix_tla_syntax_rewrites_disjoined_implication_pair_as_if_then_else() -> None:
    spec = """---- MODULE FileTransfer ----
RetransmitIfNeeded(p) ==
((retryCount[p] > 0) => SendPacket(p))
 \\/ ((retryCount[p] <= 0) =>
     (* Give up - no further action needed. *)
      UnchangedVars )
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote disjoined implication pair as IF THEN ELSE" in result.fixes_applied
    assert "((retryCount[p] > 0) => SendPacket(p))" not in result.fixed_spec
    assert "IF retryCount[p] > 0 THEN SendPacket(p) ELSE UnchangedVars" in result.fixed_spec


def test_fix_tla_syntax_inlines_standalone_next_disjunct_and_dangling_conj_lines() -> None:
    spec = """---- MODULE FileTransfer ----
Next ==
    \\/
    /\\ currentChunkIndex < FILE_LENGTH
    /\\
SendPacket(currentChunkIndex+1)
    /\\ currentChunkIndex' = currentChunkIndex + 1

\\\\/
    /\\ Len(channelBuffer) > 0
\\\\ AckReceived(msg)

\\\\/
\\A p \\in PACKET_IDS :
    RetransmitIfNeeded(p)
====
"""

    result = fix_tla_syntax(spec)

    assert "inlined standalone disjunct lines" in result.fixes_applied
    assert "merged dangling conjunction lines" in result.fixes_applied
    assert "normalized malformed backslash-leading action lines" in result.fixes_applied
    assert "\n    \\/ /\\ currentChunkIndex < FILE_LENGTH" in result.fixed_spec
    assert "\n       /\\ SendPacket(currentChunkIndex+1)" in result.fixed_spec
    assert "\n    \\/ /\\ Len(channelBuffer) > 0" in result.fixed_spec
    assert "\n       /\\ AckReceived(msg)" in result.fixed_spec
    assert "\n    \\/ \\A p \\in PACKET_IDS :" in result.fixed_spec


def test_fix_tla_syntax_rewrites_double_bracket_singleton_sequence_literal() -> None:
    spec = """---- MODULE FileTransfer ----
SendPacket(p) ==
    /\\ channelBuffer' = Append(channelBuffer, [[p]])
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote double-bracket singleton sequence literal" in result.fixes_applied
    assert "[[p]]" not in result.fixed_spec
    assert "Append(channelBuffer, <<p>>)" in result.fixed_spec


def test_fix_tla_syntax_inlines_quantified_implication_disjunct_body() -> None:
    spec = """---- MODULE FileTransfer ----
Next ==
    \\/ \\A p \\in PACKET_IDS :
    (\\E r : r=retryCount[p]) -> (
        IF retryCount[p]>0 THEN RetransmitIfNeeded(p)

       )
====
"""

    result = fix_tla_syntax(spec)

    assert "inlined quantified implication disjunct body" in result.fixes_applied
    assert "(\\E r : r=retryCount[p]) -> (" not in result.fixed_spec
    assert "completed quantified action IF missing ELSE branch" in result.fixes_applied
    assert "\\/ \\A p \\in PACKET_IDS : ((\\E r : r=retryCount[p]) => IF retryCount[p]>0 THEN RetransmitIfNeeded(p) ELSE UnchangedVars)" in result.fixed_spec


def test_fix_tla_syntax_completes_quantified_action_if_missing_else() -> None:
    spec = """---- MODULE FileTransfer ----
Next ==
    \\/ \\A p \\in PACKET_IDS : ((\\E r : r=retryCount[p]) => IF retryCount[p]>0 THEN RetransmitIfNeeded(p))

UnchangedVars == x' = x
====
"""

    result = fix_tla_syntax(spec)

    assert "completed quantified action IF missing ELSE branch" in result.fixes_applied
    assert "IF retryCount[p]>0 THEN RetransmitIfNeeded(p) ELSE UnchangedVars" in result.fixed_spec


def test_fix_tla_syntax_benchmark_shape_inlines_and_completes_quantified_action_if() -> None:
    spec = """---- MODULE FileTransfer ----
Next ==
    \\/ \\A p \\in PACKET_IDS :
    (\\E r : r=retryCount[p]) -> (
        IF retryCount[p]>0 THEN RetransmitIfNeeded(p)

       )

UnchangedVars == x' = x
====
"""

    result = fix_tla_syntax(spec)

    assert "inlined quantified implication disjunct body" in result.fixes_applied
    assert "completed quantified action IF missing ELSE branch" in result.fixes_applied
    assert "\\/ \\A p \\in PACKET_IDS : ((\\E r : r=retryCount[p]) => IF retryCount[p]>0 THEN RetransmitIfNeeded(p) ELSE UnchangedVars)" in result.fixed_spec


def test_fix_tla_syntax_late_stage_quantified_action_if_completion() -> None:
    spec = """---- MODULE FileTransfer ----
Next ==
    \\/
    /\\ currentChunkIndex < FILE_LENGTH
    /\\
SendPacket(currentChunkIndex+1)

\\\\/
\\A p \\in PACKET_IDS :
    (\\E r : r=retryCount[p]) -> (
        IF retryCount[p]>0 THEN RetransmitIfNeeded(p)

       )

UnchangedVars == x' = x
====
"""

    result = fix_tla_syntax(spec)

    assert "inlined standalone disjunct lines" in result.fixes_applied
    assert "inlined quantified implication disjunct body" in result.fixes_applied
    assert "completed quantified action IF missing ELSE branch" in result.fixes_applied
    assert "\\/ \\A p \\in PACKET_IDS : ((\\E r : r=retryCount[p]) => IF retryCount[p]>0 THEN RetransmitIfNeeded(p) ELSE UnchangedVars)" in result.fixed_spec


def test_fix_tla_syntax_normalizes_benchmark_shaped_spec_temporal_box_spacing() -> None:
    spec = """---- MODULE FileTransfer ----
Spec == Init /\\ [][ Next ]_<< sentChunks ,ackdPackets ,retryCount ,
                               currentChunkIndex ,channelBuffer >> /\\ TypeOK
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized spaced Spec temporal box" in result.fixes_applied
    assert "[][ Next ]_" not in result.fixed_spec
    assert "Spec == Init /\\ [][Next]_<< sentChunks ,ackdPackets ,retryCount ," in result.fixed_spec


def test_fix_tla_syntax_normalizes_malformed_terminating_if_condition() -> None:
    spec = """---- MODULE FileTransfer ----
Terminating ==
IF ackedPackets # PACKET_IDS \\/ \\E p:\\(p <=FILE_LENGTH) & retryCount[p]<=-1 THEN UNCHANGED <<sentChunks, ackedPackets, channelBuffer, currentChunkIndex, retryCount>> ELSE UnchangedVars
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized malformed terminating IF condition" in result.fixes_applied
    assert "\\E p:\\(" not in result.fixed_spec
    assert " & " not in result.fixed_spec
    assert "IF (ackedPackets # PACKET_IDS) \\/ (\\E p : (p <= FILE_LENGTH) /\\ retryCount[p] <= -1) THEN UNCHANGED <<sentChunks, ackedPackets, channelBuffer, currentChunkIndex, retryCount>> ELSE UnchangedVars" in result.fixed_spec


def test_fix_tla_syntax_normalizes_upper_snake_variable_aliases() -> None:
    spec = """---- MODULE FileTransfer ----
VARIABLES channelBuffer, currentChunkIndex

AckReceived(p) ==
    /\\ IF ~(p \\in CHANNEL_BUFFER) THEN currentChunkIndex' = currentChunkIndex ELSE currentChunkIndex' = currentChunkIndex
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized uppercase variable aliases" in result.fixes_applied
    assert "CHANNEL_BUFFER" not in result.fixed_spec
    assert "channelBuffer" in result.fixed_spec


def test_fix_tla_syntax_rewrites_insert_pseudo_op_as_set_union() -> None:
    spec = """---- MODULE FileTransfer ----
AckReceived(p) ==
    /\\ ackedPackets' = Insert(ackedPackets,p)
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote Insert pseudo-op as set union" in result.fixes_applied
    assert "Insert(ackedPackets,p)" not in result.fixed_spec
    assert "ackedPackets' = ackedPackets \\cup {p}" in result.fixed_spec


def test_fix_tla_syntax_infers_function_domain_from_quantified_usage() -> None:
    spec = """---- MODULE FileTransfer ----
TypeOK ==
    /\\ \\A p \\in PACKET_IDS :
         retryCount[p] \\in 0..MAX_RETRY

Init ==
    /\\ retryCount = [p |-> (IF p <= FILE_LENGTH THEN MAX_RETRY ELSE -1)]
====
"""

    result = fix_tla_syntax(spec)

    assert "added inferred domain to function initializer" in result.fixes_applied
    assert "/\\ retryCount = [p \\in PACKET_IDS |-> (IF p <= FILE_LENGTH THEN MAX_RETRY ELSE -1)]" in result.fixed_spec


def test_fix_tla_syntax_removes_unchanged_conjunct_from_typeok() -> None:
    spec = """---- MODULE FileTransfer ----
TypeOK == /\\ sentChunks \\in Seq(PACKET_IDS)
          /\\ UNCHANGED <<sentChunks>>
          /\\ ackedPackets \\subseteq PACKET_IDS
====
"""

    result = fix_tla_syntax(spec)

    assert "removed UNCHANGED conjunct from TypeOK" in result.fixes_applied
    assert "/\\ UNCHANGED <<sentChunks>>" not in result.fixed_spec
    assert "TypeOK == /\\ sentChunks \\in Seq(PACKET_IDS)" in result.fixed_spec


def test_fix_tla_syntax_moves_unchangedvars_definition_before_first_use() -> None:
    spec = """---- MODULE FileTransfer ----
RetransmitIfNeeded(p) ==
    IF retryCount[p] > 0 THEN SendPacket(p) ELSE UnchangedVars

UnchangedVars == /\\ retryCount' = retryCount
====
"""

    result = fix_tla_syntax(spec)

    assert "moved UnchangedVars definition before first use" in result.fixes_applied
    assert result.fixed_spec.index("UnchangedVars ==") < result.fixed_spec.index("RetransmitIfNeeded(p) ==")


def test_fix_tla_syntax_realigns_multiline_spec_tuple_with_variables_declaration() -> None:
    spec = """---- MODULE FileTransfer ----
VARIABLES sentChunks, ackedPackets, channelBuffer, currentChunkIndex, retryCount

Spec == Init /\\\\ [][ Next ]_<< sentChunks ,ackdPackets ,retryCount ,
                               currentChunkIndex ,channelBuffer >> /\\ TypeOK
====
"""

    result = fix_tla_syntax(spec)

    assert "realigned Spec vars tuple with VARIABLES declaration" in result.fixes_applied
    assert "Spec == Init /\\ [][Next]_<<sentChunks, ackedPackets, channelBuffer, currentChunkIndex, retryCount>> /\\ TypeOK" in result.fixed_spec


def test_fix_tla_syntax_repairs_remaining_filetransfer_semantic_artifacts_to_sany_clean() -> None:
    spec = """---- MODULE FileTransfer ----
EXTENDS Naturals, Sequences, FiniteSets, Integers

CONSTANT FILE_LENGTH, PACKET_IDS, MAX_RETRY
ASSUME FILE_LENGTH \\in Nat
ASSUME PACKET_IDS \\subseteq Nat
ASSUME MAX_RETRY \\in Nat

VARIABLES sentChunks, ackedPackets, channelBuffer, currentChunkIndex, retryCount

TypeOK == /\\ sentChunks \\in Seq(PACKET_IDS)
          /\\ ackedPackets \\subseteq PACKET_IDS
          /\\ channelBuffer \\in Seq(Seq(Nat))
          /\\ currentChunkIndex \\in Nat
          /\\ retryCount \\in [PACKET_IDS -> Int]

Init ==
    /\\ sentChunks = <<>>
    /\\ ackedPackets = {}
    /\\ retryCount = [p |-> (IF p <= FILE_LENGTH THEN MAX_RETRY ELSE -1)]
    /\\ currentChunkIndex = 0
    /\\ channelBuffer = <<>>

AckReceived(p) ==
    IF ~(p \\in channelBuffer) THEN
        UNCHANGED <<sentChunks, ackedPackets, channelBuffer, currentChunkIndex, retryCount>>
    ELSE (
        /\\ sentChunks' = sentChunks
        /\\ ackedPackets' = ackedPackets \\cup {p}
        /\\ channelBuffer' = RemoveFirstWhere(LAMBDA x : x[1] = p, channelBuffer)
        /\\ currentChunkIndex' = currentChunkIndex
        /\\ retryCount' = retryCount
    )

Next ==
    \\/ /\\ currentChunkIndex < FILE_LENGTH
       /\\ sentChunks' = sentChunks
       /\\ ackedPackets' = ackedPackets
       /\\ channelBuffer' = Append(channelBuffer, <<currentChunkIndex + 1>>)
       /\\ currentChunkIndex' = currentChunkIndex + 1
       /\\ retryCount' = [retryCount EXCEPT ![currentChunkIndex + 1] = MAX_RETRY]
    \\/ /\\ Len(channelBuffer) > 0
       /\\ AckReceived([first |-> first][currentChannel])

Spec == Init /\\ [][Next]_<<sentChunks, ackedPackets, channelBuffer, currentChunkIndex, retryCount>> /\\ TypeOK
====
"""

    result = fix_tla_syntax(spec)
    validation = validate_string(result.fixed_spec, module_name="FileTransfer")

    assert "added inferred domain to function initializer" in result.fixes_applied
    assert "defined RemoveFirstWhere helper operator" in result.fixes_applied
    assert "rewrote channel placeholder ack target as Head(channelBuffer)[1]" in result.fixes_applied
    assert validation.valid, validation.raw_output


def test_fix_tla_syntax_rewrites_nested_lambda_zero_initializer() -> None:
    spec = """---- MODULE GCounter ----
Init ==
    /\\ counts = <<>> \\/
       (\\lambda _ \\in NodeSet:
           (\\lambda _ \\in NodeSet: 0))
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote nested lambda zero initializer" in result.fixes_applied
    assert "(\\lambda _ \\in NodeSet:" not in result.fixed_spec
    assert "[i \\in NodeSet |-> [j \\in NodeSet |-> 0]]" in result.fixed_spec


def test_fix_tla_syntax_normalizes_uppercase_in_membership_in_if_guard() -> None:
    spec = """---- MODULE GCounter ----
Merge ==
    /\\ IF j IN {i} THEN MAX(counts[m][j], counts[p][j])
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized uppercase IN membership in IF guard" in result.fixes_applied
    assert "IF j \\in {i} THEN MAX(counts[m][j], counts[p][j])" in result.fixed_spec


def test_fix_tla_syntax_completes_quantified_if_assignment_missing_else() -> None:
    spec = """---- MODULE GCounter ----
Merge ==
    /\\ (\\forall i,j \\in NodeSet :
           counts[i][j]' =
               IF j \\in {i} THEN MAX(counts[m][j], counts[p][j])
====
"""

    result = fix_tla_syntax(spec)

    assert "completed quantified IF assignment missing ELSE branch" in result.fixes_applied
    assert "counts[i][j]' = IF j \\in {i} THEN MAX(counts[m][j], counts[p][j]) ELSE counts[i][j])" in result.fixed_spec


def test_fix_tla_syntax_normalizes_malformed_term_disjunct_tail() -> None:
    spec = """---- MODULE GCounter ----
Next ==
    LET term == /\\ UNCHANGED <<counts>>
    IN
        (inc(Node)) \\/
        (merge(ANY, ANY)) /\\
        term
====
"""

    result = fix_tla_syntax(spec)

    assert "normalized malformed term disjunct tail" in result.fixes_applied
    assert "(merge(ANY, ANY)) \\/" in result.fixed_spec


def test_fix_tla_syntax_auto_defines_sum_helper_for_line_start_use() -> None:
    spec = """---- MODULE GCounter ----
EXTENDS Naturals, FiniteSets
CONSTANT NodeSet
VARIABLES counts

GlobalCount ==
    Sum([n \\in NodeSet |-> counts[n]])
====
"""

    result = fix_tla_syntax(spec)

    assert "auto-defined Sum helper" in result.fixes_applied
    assert "Sum(S) ==" in result.fixed_spec


def test_fix_tla_syntax_auto_defines_max_helpers_for_binary_and_set_forms() -> None:
    spec = """---- MODULE GCounter ----
EXTENDS Naturals, FiniteSets

MergeValue ==
    MAX(a, b)

GlobalCount ==
    Max({1, 2})
====
"""

    result = fix_tla_syntax(spec)

    assert "auto-defined MAX helper" in result.fixes_applied
    assert "auto-defined Max helper" in result.fixes_applied
    assert "MAX(a, b) == IF a >= b THEN a ELSE b" in result.fixed_spec
    assert "Max(S) == CHOOSE x \\in S : \\A y \\in S : x >= y" in result.fixed_spec


def test_fix_tla_syntax_quantifies_node_and_any_placeholder_action_invocations() -> None:
    spec = """---- MODULE GCounter ----
EXTENDS Naturals, FiniteSets
CONSTANT NodeSet
VARIABLES counts

Next ==
    LET
        inc(n) ==
            /\\ UNCHANGED <<counts>>
        merge(m, p) ==
            /\\ UNCHANGED <<counts>>
        term ==
            /\\ UNCHANGED <<counts>>
    IN
        (inc(Node)) \\/
        (merge(ANY, ANY)) \\/
        term
====
"""

    result = fix_tla_syntax(spec)

    assert "rewrote Node placeholder action invocation as quantified choice" in result.fixes_applied
    assert "rewrote ANY placeholder action invocation as quantified choice" in result.fixes_applied
    assert "(\\E n \\in NodeSet : inc(n)) \\/" in result.fixed_spec
    assert "(\\E m \\in NodeSet : \\E p \\in NodeSet : merge(m, p)) \\/" in result.fixed_spec
    sany_result = validate_string(result.fixed_spec, module_name="GCounter")
    assert sany_result.valid, sany_result.raw_output


def test_fix_tla_syntax_makes_bm005_shape_sany_valid() -> None:
    spec = """---- MODULE BoundedFIFO ----

EXTENDS Naturals, Sequences

CONSTANT K

VARIABLE q, head, item, q, size, tail
          head
          tail
          size

vars == <<q, head, tail, size>>

TypeOk ==
    /\\ q \\subseteq Nat
       /\\ Len(q) = size
       /\\ head \\in 1 .. K + 1
       /\\ tail \\in 1 .. K + 1
       /\\ size \\in 0 .. K

Init ==
    /\\ q = []
    /\\ head = 1
    /\\ tail = 2
    /\\ size = 0

ProducerAction(item) ==
    LET newTail == IF tail # K THEN tail + 1 ELSE 1 IN
        /\\ size < K
        /\\ item' \\notin q
        /\\ q' = Append(SeqSubseq(q, 1..size), SeqFromList([item]))
        /\\ head' = head
        /\\ tail' = newTail
        /\\ size' = size + 1

ConsumerAction ==
    LET oldHeadVal == SubSequence(q, head-1, head)
          nextIndex == IF head # K THEN head + 1 ELSE 1 IN
        /\\ size > 0
        /\\ q' = RemoveAt(head - 1)(q)
           \\/ UNCHANGED <<head>>

Next ==
    \\E item \\in Nat :
        ProducerAction(item)

\\vee
    ConsumerAction

Spec == Init /\\
        [][ Next ]_vars \\
        /\\ TypeOk

====
"""

    result = fix_tla_syntax(spec)

    assert "normalized sequence helper aliases" in result.fixes_applied
    assert "removed primes from operator parameters" in result.fixes_applied
    assert "removed shadowed variable names from declaration" in result.fixes_applied
    sany_result = validate_string(result.fixed_spec, module_name="BoundedFIFO")
    assert sany_result.valid, sany_result.raw_output
