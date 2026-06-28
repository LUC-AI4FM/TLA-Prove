---- MODULE TwoPhaseCommit ----
EXTENDS Integers

CONSTANT N
ASSUME N \in 1..10

VARIABLES coordState, partState, decision

Parts == 1..N

TypeOK ==
    /\ coordState \in {"init", "waiting", "committed", "aborted"}
    /\ partState \in [Parts -> {"working", "prepared", "aborted", "committed"}]
    /\ decision \in {"none", "commit", "abort"}

Init ==
    /\ coordState = "init"
    /\ partState = [p \in Parts |-> "working"]
    /\ decision = "none"

Prepare ==
    /\ coordState = "init"
    /\ coordState' = "waiting"
    /\ UNCHANGED <<partState, decision>>

VoteYes(p) ==
    /\ coordState = "waiting"
    /\ partState[p] = "working"
    /\ partState' = [partState EXCEPT ![p] = "prepared"]
    /\ UNCHANGED <<coordState, decision>>

VoteNo(p) ==
    /\ coordState = "waiting"
    /\ partState[p] = "working"
    /\ partState' = [partState EXCEPT ![p] = "aborted"]
    /\ UNCHANGED <<coordState, decision>>

DecideCommit ==
    /\ coordState = "waiting"
    /\ \A p \in Parts : partState[p] = "prepared"
    /\ decision' = "commit"
    /\ coordState' = "committed"
    /\ UNCHANGED partState

DecideAbort ==
    /\ coordState = "waiting"
    /\ \E p \in Parts : partState[p] = "aborted"
    /\ decision' = "abort"
    /\ coordState' = "aborted"
    /\ UNCHANGED partState

CommitPart(p) ==
    /\ decision = "commit"
    /\ partState[p] = "prepared"
    /\ partState' = [partState EXCEPT ![p] = "committed"]
    /\ UNCHANGED <<coordState, decision>>

AbortPart(p) ==
    /\ decision = "abort"
    /\ partState[p] \in {"prepared", "working"}
    /\ partState' = [partState EXCEPT ![p] = "aborted"]
    /\ UNCHANGED <<coordState, decision>>

Done ==
    /\ coordState \in {"committed", "aborted"}
    /\ \A p \in Parts : partState[p] \in {"committed", "aborted"}
    /\ UNCHANGED <<coordState, partState, decision>>

Next ==
    \/ Prepare
    \/ \E p \in Parts : VoteYes(p) \/ VoteNo(p)
    \/ DecideCommit
    \/ DecideAbort
    \/ \E p \in Parts : CommitPart(p) \/ AbortPart(p)
    \/ Done

Consistency ==
    \A p \in Parts :
        partState[p] = "committed" => decision = "commit"

vars == <<coordState, partState, decision>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK Consistency
\* CONSTANT N = 3
