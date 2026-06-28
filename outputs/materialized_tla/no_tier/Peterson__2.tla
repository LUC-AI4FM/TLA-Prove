---- MODULE Peterson ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES turn, flag

Init == /\ turn = 0
        /\ flag = <<FALSE, FALSE>>

Next == \/ /\ flag[1] = FALSE
           /\ flag' = <<TRUE, flag[2]>>
           /\ turn' = 2
       \/ /\ flag[2] = FALSE
           /\ flag' = <<flag[1], TRUE>>
           /\ turn' = 1
       \/ /\ flag' = <<FALSE, FALSE>>
           /\ turn' = turn

Spec == Init /\ [][Next]_<<turn, flag>>

====
