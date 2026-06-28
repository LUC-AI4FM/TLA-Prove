---- MODULE Toggle ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES state

Init == /\ state = 0

Next == \/ /\ state = 0
          /\ state' = 1
       \/ /\ state = 1
          /\ state' = 0

Spec == Init /\ [][Next]_<<state>>

====
