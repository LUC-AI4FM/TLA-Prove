---- MODULE RingLeader ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N
ASSUME N \in 1..10

VARIABLES state, leader

TypeOK == /\ state \in [1..N -> {"idle", "active", "leader"}]
          /\ leader \in 1..N \cup {0}

Init == /\ state = [i \in 1..N |-> "idle"]
        /\ leader = 0

Next == 
  \/ \E i \in 1..N :
        /\ state[i] = "idle"
        /\ state' = [state EXCEPT ![i] = "active"]
        /\ leader' = leader
  \/ \E i \in 1..N :
        /\ state[i] = "active"
        /\ state' = [state EXCEPT ![i] = "leader"]
        /\ leader' = i
  \/ UNCHANGED <<state, leader>>

Spec == Init /\ [][Next]_<<state, leader>>

====
