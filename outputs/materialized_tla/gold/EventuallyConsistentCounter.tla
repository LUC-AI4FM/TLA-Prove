---- MODULE EventuallyConsistentCounter ----
EXTENDS Integers, Sequences, FiniteSets
CONSTANTS Node

VARIABLES counts

Init == /\ counts = [n \in Node |-> [m \in Node |-> 0]]

Next == \/ \E n \in Node:
          /\ counts' = [counts EXCEPT ![n] = [m \in Node |-> 0]]
          \/ \E m \in Node:
              /\ counts' = [counts EXCEPT ![n][m] = counts[n][m] + 1]
              /\ \A k \in Node: counts'[n][k] = counts[n][k]

Spec == Init /\ [][Next]_<<counts>>

====
