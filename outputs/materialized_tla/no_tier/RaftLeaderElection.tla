---- MODULE RaftLeaderElection ----
EXTENDS Integers, Sequences, FiniteSets
CONSTANTS NULL, Server

VARIABLES currentTerm, votedFor, state

Leader == "Leader"
Candidate == "Candidate"
Follower == "Follower"

Init ==
  /\ currentTerm = 0
  /\ votedFor = [s \in Server |-> NULL]
  /\ state = [s \in Server |-> Follower]

Next ==
  \/ \E s \in Server :
       /\ state[s] = Follower
       /\ currentTerm' = currentTerm + 1
       /\ votedFor' = [votedFor EXCEPT ![s] = s]
       /\ state' = [state EXCEPT ![s] = Candidate]
  \/ \E s \in Server :
       /\ state[s] = Candidate
       /\ currentTerm' = currentTerm
       /\ votedFor' = votedFor
       /\ state' = state
  \/ \E s \in Server :
       /\ state[s] = Leader
       /\ currentTerm' = currentTerm
       /\ votedFor' = votedFor
       /\ state' = state

Spec == Init /\ [][Next]_<<currentTerm, votedFor, state>>

====
