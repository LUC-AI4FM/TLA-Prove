---- MODULE Register ----
EXTENDS Naturals, TLC

CONSTANTS N

VARIABLES reg

Init == reg = 0

Next == \/ reg' = 0
        \/ \E n \in 0..N : reg' = n

Spec == Init /\ [][Next]_reg

====
