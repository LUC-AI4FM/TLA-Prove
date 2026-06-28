---- MODULE DistLock ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N, Nodes
VARIABLES lockOwner


vars == << lockOwner >>

Init == /\ lockOwner = 0

Acquire(n) == /\ lockOwner = 0
              /\ lockOwner' = n

Release(n) == /\ lockOwner = n
              /\ lockOwner' = 0

Next == \E n \in Nodes : Acquire(n) \/ Release(n)

Spec == Init /\ [][Next]_vars

====
