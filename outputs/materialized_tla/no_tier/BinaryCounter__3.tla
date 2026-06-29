---- MODULE BinaryCounter ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES counter

Init == /\ counter \in 0..3

Next == /\ counter' \in 0..3
        /\ counter' = (counter + 1) % 4

Spec == Init /\ [][Next]_<<counter>> ====
