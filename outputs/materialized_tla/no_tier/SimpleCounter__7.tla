---- MODULE SimpleCounter ----
EXTENDS Naturals, TLC

CONSTANT MAX

VARIABLE counter

TypeOK == counter \in 0..MAX

Init == counter = 0

Next == counter' = IF counter < MAX THEN counter + 1 ELSE counter

Spec == Init /\ [][Next]_<<counter>> /\ TypeOK

====
