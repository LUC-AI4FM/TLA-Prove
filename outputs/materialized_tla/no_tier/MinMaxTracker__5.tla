---- MODULE MinMaxTracker ----
EXTENDS Naturals, TLC

CONSTANTS N

VARIABLES minVal, maxVal

Init == 
    /\ minVal = 0
    /\ maxVal = 0

Next == 
    /\ \E val \in 0..N : 
        /\ minVal' = IF val < minVal THEN val ELSE minVal
        /\ maxVal' = IF val > maxVal THEN val ELSE maxVal
    /\ UNCHANGED << minVal, maxVal >>

Spec == Init /\ [][Next]_<<minVal, maxVal>>

TypeOK == 
    /\ minVal \in 0..N
    /\ maxVal \in 0..N

====
