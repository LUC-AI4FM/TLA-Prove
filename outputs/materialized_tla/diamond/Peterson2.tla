---- MODULE Peterson2 ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES flag, turn

TypeOK == /\ flag \in [1..2 -> BOOLEAN]
          /\ turn \in 1..2

Init == /\ flag = [x \in 1..2 |-> FALSE]
        /\ turn = 1

Next == \/ /\ flag' = [flag EXCEPT ![1] = FALSE]
          /\ turn' = turn
        \/ /\ flag' = [flag EXCEPT ![2] = FALSE]
          /\ turn' = turn
        \/ /\ flag' = [flag EXCEPT ![1] = TRUE]
          /\ turn' = 2
        \/ /\ flag' = [flag EXCEPT ![2] = TRUE]
          /\ turn' = 1

Spec == Init /\ [][Next]_<<flag, turn>>

====
