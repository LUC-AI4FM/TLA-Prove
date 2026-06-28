---- MODULE RaftElection ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N, majority, NULL

VARIABLES currentTerm, votedFor, state

Init == /\ currentTerm = 0
        /\ votedFor = [i \in 1..N |-> NULL]
        /\ state = [i \in 1..N |-> "Follower"]

Next == 
    \E i \in 1..N :
        \/ /\ state[i] = "Follower"
           /\ currentTerm' = currentTerm + 1
           /\ votedFor' = [votedFor EXCEPT ![i] = i]
           /\ state' = [state EXCEPT ![i] = "Candidate"]
        \/ /\ state[i] = "Candidate"
           /\ currentTerm' = currentTerm
           /\ votedFor' = votedFor
           /\ state' = state
        \/ /\ state[i] = "Leader"
           /\ currentTerm' = currentTerm
           /\ votedFor' = votedFor
           /\ state' = state

Spec == Init /\ [][Next]_<<currentTerm, votedFor, state>>

TypeOK == /\ currentTerm \in Nat
          /\ votedFor \in [1..N -> 1..N \cup {NULL}]
          /\ state \in [1..N -> {"Follower", "Candidate", "Leader"}]

====
