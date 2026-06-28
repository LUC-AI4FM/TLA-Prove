---- MODULE Counter ----
EXTENDS Naturals

VARIABLE counter

CONSTANT MAX

Init == 
    counter = 0

Increment == 
    counter' = counter + 1

Next == 
    /\ counter <= MAX
    /\ Increment
    \/ UNCHANGED <<counter>>

Spec == 
    Init /\ [][Next]_<<counter>>

====
