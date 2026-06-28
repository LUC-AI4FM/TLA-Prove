---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLE state

Init == /\ state = [i \in 1..N |-> "idle"]

Next == \/ \E i \in 1..N :
          /\ state[i] = "idle"
          /\ state' = [state EXCEPT ![i] = "trying"]
        \/ \E i \in 1..N :
          /\ state[i] = "trying"
          /\ \A j \in 1..N : j # i => state[j] # "critical"
          /\ state' = [state EXCEPT ![i] = "critical"]
        \/ \E i \in 1..N :
          /\ state[i] = "critical"
          /\ state' = [state EXCEPT ![i] = "idle"]

Spec == Init /\ [][Next]_<<state>>

TypeOK == /\ state \in [1..N -> {"idle", "trying", "critical"}]
====
