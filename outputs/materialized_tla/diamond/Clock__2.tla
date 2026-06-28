---- MODULE Clock ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES clock, MAX

Init == /\ clock = 0
        /\ MAX = 10

Next == /\ clock' = IF clock = MAX THEN 0 ELSE clock + 1
        /\ MAX' = MAX

Spec == Init /\ [][Next]_<<clock, MAX>>

TypeOK == /\ clock \in 0..MAX
          /\ MAX \in 0..100

====
