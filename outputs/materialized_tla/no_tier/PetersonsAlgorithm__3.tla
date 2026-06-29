---- MODULE PetersonsAlgorithm ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLE flag, turn

Init == /\ flag = [i \in 1..2 |-> FALSE]
        /\ turn = 1

Next == \/ /\ flag' = [flag EXCEPT ![1] = TRUE]
          /\ turn' = 2
          /\ UNCHANGED <<turn, flag[2]>>
        \/ /\ flag' = [flag EXCEPT ![2] = TRUE]
          /\ turn' = 1
          /\ UNCHANGED <<turn, flag[1]>>
        \/ /\ flag' = [flag EXCEPT ![1] = FALSE]
          /\ UNCHANGED <<turn, flag[2]>>
        \/ /\ flag' = [flag EXCEPT ![2] = FALSE]
          /\ UNCHANGED <<turn, flag[1]>>

Spec == Init /\ [][Next]_<<flag, turn>>

====
