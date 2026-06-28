---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets
CONSTANTS N

VARIABLES state, turn



TypeOK == /\ state \in [1..N -> {"idle", "trying", "critical"}]
          /\ turn \in 1..N

Init == /\ state = [i \in 1..N |-> "idle"]
        /\ turn = 1

Next == \/ \E i \in 1..N :
            /\ state[i] = "idle"
            /\ state' = [state EXCEPT ![i] = "trying"]
            /\ UNCHANGED turn
        \/ \E i \in 1..N :
            /\ state[i] = "trying"
            /\ turn = i
            /\ state' = [state EXCEPT ![i] = "critical"]
            /\ UNCHANGED turn
        \/ \E i \in 1..N :
            /\ state[i] = "critical"
            /\ state' = [state EXCEPT ![i] = "idle"]
            /\ turn' = IF i = N THEN 1 ELSE i + 1

Spec == Init /\ [][Next]_<<state, turn>>

====
