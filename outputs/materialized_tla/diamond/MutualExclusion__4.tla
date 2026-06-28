---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets
CONSTANTS N

VARIABLES state, turn

Init == /\ state = [p \in 1..N |-> "idle"]
        /\ turn = 1

Next == \/ /\ turn' = turn + 1
           /\ turn' <= N
           /\ state' = [state EXCEPT ![turn] = "critical"]
       \/ /\ turn' = turn
           /\ state' = [state EXCEPT ![turn] = "idle"]

Spec == Init /\ [][Next]_<<state, turn>>

TypeOK == /\ state \in [1..N -> {"idle", "trying", "critical"}]
         /\ turn \in 1..N

====
