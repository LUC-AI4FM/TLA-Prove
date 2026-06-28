---- MODULE TokenRing ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES tokenHolder, inCS

Init == 
    /\ tokenHolder \in 1..N
    /\ inCS \in 1..N

Next == 
    /\ tokenHolder' \in 1..N
    /\ inCS' \in 1..N
    /\ tokenHolder' = tokenHolder
        \/ tokenHolder' = IF tokenHolder = N THEN 1 ELSE tokenHolder + 1
    /\ inCS' = inCS
        \/ /\ inCS' = tokenHolder
            /\ inCS = tokenHolder
        \/ /\ inCS' = tokenHolder
            /\ inCS \in 1..N
            /\ inCS' # tokenHolder

Spec == Init /\ [][Next]_<<tokenHolder, inCS>>

====
