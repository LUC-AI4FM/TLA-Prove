---- MODULE Barrier ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES barrierCount, barrierFlag

Init == /\ barrierCount = 0
        /\ barrierFlag = FALSE

Next == /\ barrierCount' = IF barrierCount = N-1 THEN 0 ELSE barrierCount + 1
        /\ barrierFlag' = IF barrierCount' = 0 THEN FALSE ELSE barrierFlag

Spec == Init /\ [][Next]_<<barrierCount, barrierFlag>>

====
