---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N
ASSUME N \in Nat /\ N > 0

VARIABLES state

(* State of each process: idle, trying, critical *)
State == {"idle", "trying", "critical"}

(* Initial state: all processes idle *)
Init == /\ state \in [1..N -> State]
        /\ \A i \in 1..N : state[i] = "idle"

(* Transition: a process can move from idle to trying,
   from trying to critical if no other is critical,
   from critical to idle *)
Next ==
  \E i \in 1..N :
    \/ /\ state[i] = "idle"
       /\ state' = [state EXCEPT ![i] = "trying"]
    \/ /\ state[i] = "trying"
       /\ \A j \in 1..N : j # i => state[j] # "critical"
       /\ state' = [state EXCEPT ![i] = "critical"]
    \/ /\ state[i] = "critical"
       /\ state' = [state EXCEPT ![i] = "idle"]
    /\ UNCHANGED <<>> (* no other variable changes *)

(* Mutual exclusion invariant: at most one process in critical *)
TypeOK == /\ state \in [1..N -> State]
           /\ \A i, j \in 1..N : i # j => state[i] # "critical" \/ state[j] # "critical"

Spec == Init /\ [][Next]_<<state>>

====
