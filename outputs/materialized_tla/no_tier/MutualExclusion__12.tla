---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES state



TypeOK == /\ state \in [1..N -> {"idle", "trying", "critical"}]
           /\ \A i \in 1..N: state[i] \in {"idle", "trying", "critical"}

Init == /\ state = [i \in 1..N |-> "idle"]

Next == \E i \in 1..N:
          /\ state' = [state EXCEPT ![i] = "trying"]
          \/ state' = [state EXCEPT ![i] = "critical"]
          \/ state' = [state EXCEPT ![i] = "idle"]

Spec == Init /\ [][Next]_<<state>>

====
