---- MODULE BinaryCounter ----
EXTENDS Integers, Sequences

VARIABLES counter

Init == counter = 0

Next == /\ counter' = (counter + 1) % 4

Spec == Init /\ [][Next]_<<counter>>

====
