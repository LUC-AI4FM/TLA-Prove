---- MODULE PetersonsAlgorithm ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES flag, turn

Init == /\ flag = [i \in 1..2 |-> FALSE]
        /\ turn = 1

Next == \/ /\ flag[1] = FALSE
          /\ flag[2] = FALSE
          /\ flag[1] = TRUE
          /\ turn' = 2
          /\ flag' = [flag EXCEPT ![2] = FALSE]
        \/ /\ flag[1] = FALSE
          /\ flag[2] = FALSE
          /\ flag[2] = TRUE
          /\ turn' = 1
          /\ flag' = [flag EXCEPT ![1] = FALSE]
        \/ /\ flag[1] = TRUE
          /\ turn = 2
          /\ flag[2] = TRUE
          /\ flag' = [flag EXCEPT ![1] = FALSE]
        \/ /\ flag[2] = TRUE
          /\ turn = 1
          /\ flag[1] = TRUE
          /\ flag' = [flag EXCEPT ![2] = FALSE]
        \/ /\ flag[1] = TRUE
          /\ turn = 2
          /\ flag[2] = FALSE
          /\ flag' = [flag EXCEPT ![1] = FALSE]
        \/ /\ flag[2] = TRUE
          /\ turn = 1
          /\ flag[1] = FALSE
          /\ flag' = [flag EXCEPT ![2] = FALSE]
        \/ /\ flag[1] = TRUE
          /\ flag[2] = FALSE
          /\ turn' = 1
          /\ flag' = [flag EXCEPT ![1] = FALSE]
        \/ /\ flag[2] = TRUE
          /\ flag[1] = FALSE
          /\ turn' = 2
          /\ flag' = [flag EXCEPT ![2] = FALSE]
        \/ /\ flag[1] = FALSE
          /\ flag[2] = FALSE
          /\ turn' = turn
          /\ flag' = flag

Spec == Init /\ [][Next]_<<flag, turn>>

====
