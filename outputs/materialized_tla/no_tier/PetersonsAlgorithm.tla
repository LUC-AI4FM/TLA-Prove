---- MODULE PetersonsAlgorithm ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES flag, turn

Init == /\ flag = [i \in 1..2 |-> FALSE]
        /\ turn = 1

Next == \/ /\ flag[1] = FALSE
          /\ flag[2] = FALSE
          /\ flag' = [i \in 1..2 |-> FALSE]
          /\ turn' = turn
        \/ /\ flag[1] = FALSE
          /\ flag[2] = TRUE
          /\ turn' = 2
          /\ flag' = [i \in 1..2 |-> IF i = 2 THEN TRUE ELSE flag[i]]
        \/ /\ flag[1] = TRUE
          /\ flag[2] = FALSE
          /\ turn' = 1
          /\ flag' = [i \in 1..2 |-> IF i = 1 THEN TRUE ELSE flag[i]]
        \/ /\ flag[1] = TRUE
          /\ flag[2] = TRUE
          /\ turn' = turn
          /\ flag' = flag

Spec == Init /\ [][Next]_<<flag, turn>>

====
