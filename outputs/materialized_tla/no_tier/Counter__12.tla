---- MODULE Counter ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES count, MAX

Init == /\ count = 0
        /\ MAX = 10

Next == \/ /\ count < MAX
          /\ count' = count + 1
          /\ MAX' = MAX
      \/ /\ count = MAX
          /\ count' = count
          /\ MAX' = MAX

Spec == Init /\ [][Next]_<<count, MAX>>

====
