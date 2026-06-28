---- MODULE KeyValueStore ----
EXTENDS Integers

CONSTANT N
ASSUME N \in 1..5

Keys == 1..N
Values == 1..N

VARIABLES store, lastGet

TypeOK ==
    /\ store \in [Keys -> Values \cup {0}]
    /\ lastGet \in [Keys -> Values \cup {0}]

Init ==
    /\ store = [k \in Keys |-> 0]
    /\ lastGet = [k \in Keys |-> 0]

Put(k, v) ==
    /\ k \in Keys
    /\ v \in Values
    /\ store' = [store EXCEPT ![k] = v]
    /\ UNCHANGED lastGet

Get(k) ==
    /\ k \in Keys
    /\ lastGet' = [lastGet EXCEPT ![k] = store[k]]
    /\ UNCHANGED store

Next == \E k \in Keys :
    (\E v \in Values : Put(k, v)) \/ Get(k)

Linearizability == \A k \in Keys : lastGet[k] = store[k] \/ lastGet[k] = 0

vars == <<store, lastGet>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK Linearizability
\* CONSTANT N = 2
