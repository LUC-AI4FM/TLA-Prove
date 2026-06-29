---- MODULE KVStore ----
EXTENDS Integers, Sequences, FiniteSets
CONSTANTS NULL, N

VARIABLES store

Init == store = [k \in 0..N |-> NULL]

Next == \/ /\ \E k \in 0..N : \E v \in 0..N : store' = [store EXCEPT ![k] = v]
        \/ /\ \E k \in 0..N : store' = [store EXCEPT ![k] = NULL]
        \/ store' = store

Spec == Init /\ [][Next]_<<store>>

====
