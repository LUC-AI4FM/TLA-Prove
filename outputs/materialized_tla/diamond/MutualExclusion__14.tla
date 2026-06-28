---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N

VARIABLES state, turn

(* State variables *)

(* Initial state *)
Init == /\ state = [p \in 1..N |-> "idle"]
        /\ turn \in 1..N

(* Next-state relation *)
Next == \/ (* Process p attempts to enter critical section *)
          /\ \E p \in 1..N : /\ state[p] = "idle"
                            /\ state' = [state EXCEPT ![p] = "trying"]
                            /\ turn' = turn
          \/ (* Process p enters critical section *)
          /\ \E p \in 1..N : /\ state[p] = "trying"
                            /\ turn = p
                            /\ state' = [state EXCEPT ![p] = "critical"]
                            /\ turn' = turn
          \/ (* Process p exits critical section *)
          /\ \E p \in 1..N : /\ state[p] = "critical"
                            /\ state' = [state EXCEPT ![p] = "idle"]
                            /\ turn' = turn

(* Invariant: at most one process is in critical section *)
TypeOK == /\ state \in [1..N -> {"idle", "trying", "critical"}]
          /\ turn \in 1..N
          /\ \A p, q \in 1..N : (p /= q) => (state[p] # "critical" \/ state[q] # "critical")

Spec == Init /\ [][Next]_<<state, turn>>

====
