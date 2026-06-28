---- MODULE RingLeader ----
EXTENDS Integers, Sequences

CONSTANT N
ASSUME N \in 1..10

VARIABLES proc, leader

TypeOK == /\ proc \in 1..N
          /\ leader \in 1..N

Init == /\ proc = 1
        /\ leader = 1

Next == /\ proc' = IF proc < N THEN proc + 1 ELSE 1
        /\ leader' = IF proc = N THEN leader ELSE leader

Spec == Init /\ [][Next]_<<proc, leader>>

====
