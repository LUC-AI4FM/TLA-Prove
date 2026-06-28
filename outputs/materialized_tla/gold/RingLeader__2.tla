---- MODULE RingLeader ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N, IDs

VARIABLES leader, active

TypeOK == /\ leader \in 1..N
        /\ active \in 1..N

Init == /\ leader = 1
       /\ active = 1

Next ==
  /\ leader' = IF active = N THEN 1 ELSE leader
  /\ active' = IF active = N THEN 1 ELSE active + 1

Spec == Init /\ [][Next]_<<leader, active>>

====
