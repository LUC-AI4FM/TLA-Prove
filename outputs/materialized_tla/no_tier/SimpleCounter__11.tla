---- MODULE SimpleCounter ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT MAX

VARIABLE counter

Init == counter = 0

Next == /\ counter <= MAX
       /\ counter' = IF counter < MAX THEN counter + 1 ELSE counter

TypeOK == /\ counter \in 0..MAX

Spec == Init /\ [][Next]_<<counter>>

====
