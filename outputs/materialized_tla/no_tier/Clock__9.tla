---- MODULE
 Clock ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT MAX

VARIABLES time, max

Init == /\ time = 0
        /\ max = MAX

Next == /\ time' = IF time = max THEN 0 ELSE time + 1
        /\ max' = max

Spec == Init /\ [][Next]_<<time, max>>

TypeOK == /\ time \in Int
          /\ max \in Int

====
