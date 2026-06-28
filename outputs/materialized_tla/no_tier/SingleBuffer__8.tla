---- MODULE SingleBuffer ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES buffer, full, empty

Init == 
    /\ buffer = <<>>
    /\ full = FALSE
    /\ empty = TRUE

Next == 
    \/ /\ full = FALSE
       /\ empty = TRUE
       /\ buffer' = Append(buffer, 1)
       /\ full' = TRUE
       /\ empty' = FALSE
    \/ /\ full = TRUE
       /\ empty = FALSE
       /\ buffer' = <<>>
       /\ full' = FALSE
       /\ empty' = TRUE

Spec == Init /\ [][Next]_<<buffer, full, empty>>

====
