---- MODULE SingleBuffer ----
EXTENDS Integers, Sequences

VARIABLES buf, full

Init == 
    /\ buf = <<>>
    /\ full = FALSE

Next == 
    \/ /\ full = FALSE
       /\ buf' = <<1>>
       /\ full' = TRUE
    \/ /\ full = TRUE
       /\ buf' = <<>>
       /\ full' = FALSE

Spec == Init /\ [][Next]_<<buf, full>>

====
