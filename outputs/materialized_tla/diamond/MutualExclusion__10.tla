---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets
CONSTANTS N

VARIABLES state, turn

Init == /\ state = [p \in 1..N |-> "idle"]
        /\ turn = 1

Next == \/ /\ state[turn] = "idle"
          /\ state' = [state EXCEPT ![turn] = "critical"]
          /\ turn' = turn
        \/ /\ state[turn] # "idle"
          /\ turn' = %(turn, N) + 1
          /\ state' = state

Spec == Init /\ [][Next]_<<state, turn>>

TypeOK == /\ state \in [1..N -> {"idle", "trying", "critical"}]
          /\ turn \in 1..N

====
