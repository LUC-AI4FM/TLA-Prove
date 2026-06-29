---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets
CONSTANTS N

VARIABLES state, flag, turn

(* State of each process: idle, trying, critical *)
State == {"idle", "trying", "critical"}

(* Initial state: all processes idle, no flags set, turn arbitrary *)
Init == /\ state \in [1..N -> State]
        /\ flag \in [1..N -> BOOLEAN]
        /\ turn \in 1..N
        /\ \A i \in 1..N: state[i] = "idle" /\ flag[i] = FALSE

(* Next-state relation: process i can move from idle to trying, from trying to critical if turn = i, from critical to idle *)
Next == \E i \in 1..N:
          \/ /\ state[i] = "idle"
             /\ state' = [state EXCEPT ![i] = "trying"]
             /\ flag' = [flag EXCEPT ![i] = TRUE]
             /\ turn' = turn
          \/ /\ state[i] = "trying"
             /\ turn = i
             /\ state' = [state EXCEPT ![i] = "critical"]
             /\ flag' = flag
             /\ turn' = turn
          \/ /\ state[i] = "critical"
             /\ state' = [state EXCEPT ![i] = "idle"]
             /\ flag' = [flag EXCEPT ![i] = FALSE]
             /\ turn' = turn

Spec == Init /\ [][Next]_<<state, flag, turn>>

(* Mutual exclusion: no two processes in critical section simultaneously *)
TypeOK == \A i, j \in 1..N: i # j => ~(state[i] = "critical" /\ state[j] = "critical")

====
