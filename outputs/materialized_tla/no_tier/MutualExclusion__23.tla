---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets
CONSTANTS N

VARIABLES state, turn

Init == 
  /\ state = [p \in 1..N |-> "idle"]
  /\ turn = 1

Next == 
  \E p \in 1..N :
    \/ /\ state[p] = "idle"
       /\ state' = [state EXCEPT ![p] = "trying"]
       /\ turn' = turn
    \/ /\ state[p] = "trying"
       /\ turn = p
       /\ state' = [state EXCEPT ![p] = "critical"]
    \/ /\ state[p] = "critical"
       /\ state' = [state EXCEPT ![p] = "idle"]
    /\ UNCHANGED turn

Spec == Init /\ [][Next]_<<state, turn>>

TypeOK == 
  /\ state \in [1..N -> {"idle", "trying", "critical"}]
  /\ turn \in 1..N

====
