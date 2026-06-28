---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences

CONSTANTS N

VARIABLES state

vars == << state >>

Init == /\ state \in [1..N -> {"idle", "trying", "critical"}]
          /\ \A i \in 1..N : state[i] = "idle"

Next == \E i \in 1..N :
          /\ state' = [state EXCEPT ![i] = "trying"]
          \/ /\ state[i] = "trying"
              /\ state' = [state EXCEPT ![i] = "critical"]
          \/ /\ state[i] = "critical"
              /\ state' = [state EXCEPT ![i] = "idle"]

Spec == Init /\ []([Next]_vars)

====
