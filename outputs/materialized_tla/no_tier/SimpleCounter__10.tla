---- MODULE SimpleCounter ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES count, finished

Init == /\ count = 0
        /\ finished = FALSE

Next == \/ /\ finished = FALSE
          /\ count < 5
          /\ count' = count + 1
          /\ finished' = FALSE
      \/ /\ finished = FALSE
          /\ count = 5
          /\ count' = count
          /\ finished' = TRUE
      \/ /\ finished = TRUE
          /\ count' = count
          /\ finished' = TRUE

Spec == Init /\ [][Next]_<<count, finished>>

====
