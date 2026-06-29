---- MODULE SnapshotIsolation ----
EXTENDS Integers, FiniteSets

CONSTANT N
ASSUME N \in 1..3

Keys == 1..N
Txns == 1..N

VARIABLES db, txState, txSnapshot, txWrites

TypeOK ==
    /\ db \in [Keys -> 0..5]
    /\ txState \in [Txns -> {"idle", "active", "committed", "aborted"}]
    /\ txSnapshot \in [Txns -> [Keys -> 0..5]]
    /\ txWrites \in [Txns -> SUBSET Keys]

Init ==
    /\ db = [k \in Keys |-> 0]
    /\ txState = [t \in Txns |-> "idle"]
    /\ txSnapshot = [t \in Txns |-> [k \in Keys |-> 0]]
    /\ txWrites = [t \in Txns |-> {}]

Begin(t) ==
    /\ txState[t] = "idle"
    /\ txState' = [txState EXCEPT ![t] = "active"]
    /\ txSnapshot' = [txSnapshot EXCEPT ![t] = db]
    /\ txWrites' = [txWrites EXCEPT ![t] = {}]
    /\ UNCHANGED db

Write(t, k) ==
    /\ txState[t] = "active"
    /\ k \in Keys
    /\ txWrites' = [txWrites EXCEPT ![t] = @ \cup {k}]
    /\ UNCHANGED <<db, txState, txSnapshot>>

Commit(t) ==
    /\ txState[t] = "active"
    /\ \A t2 \in Txns :
        (t2 # t /\ txState[t2] = "committed")
            => txWrites[t] \cap txWrites[t2] = {}
    /\ db' = [k \in Keys |->
        IF k \in txWrites[t] THEN txSnapshot[t][k] + 1 ELSE db[k]]
    /\ txState' = [txState EXCEPT ![t] = "committed"]
    /\ UNCHANGED <<txSnapshot, txWrites>>

Abort(t) ==
    /\ txState[t] = "active"
    /\ txState' = [txState EXCEPT ![t] = "aborted"]
    /\ UNCHANGED <<db, txSnapshot, txWrites>>

Done ==
    /\ \A t \in Txns : txState[t] \in {"committed", "aborted"}
    /\ UNCHANGED <<db, txState, txSnapshot, txWrites>>

Next == (\E t \in Txns :
    Begin(t) \/ (\E k \in Keys : Write(t, k)) \/ Commit(t) \/ Abort(t)) \/ Done

NoWriteConflict ==
    \A t1, t2 \in Txns :
        (t1 # t2 /\ txState[t1] = "committed" /\ txState[t2] = "committed")
            => txWrites[t1] \cap txWrites[t2] = {}

vars == <<db, txState, txSnapshot, txWrites>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK NoWriteConflict
\* CONSTANT N = 2
