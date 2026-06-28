---- MODULE Counter ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES count, max

Init == /\ count = 0
        /\ max = 10

Next == \/ /\ count < max
          /\ count' = count + 1
          /\ max' = max
        \/ /\ count = max
          /\ count' = count
          /\ max' = max

Spec == Init /\ [][Next]_<<count, max>>

====
