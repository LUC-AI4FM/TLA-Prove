---- MODULE BoolFlag ----
EXTENDS Integers, Sequences, FiniteSets, TLC

VARIABLE flag

Bool == {TRUE, FALSE}

Init == flag \in Bool

Next == /\ flag' = IF flag = TRUE THEN FALSE ELSE TRUE

Spec == Init /\ [][Next]_<<flag>>

====
