---- MODULE Peterson ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES turn, flag, state

Init == /\ turn = 0
        /\ flag = [i \in 1..2 |-> FALSE]
        /\ state = [i \in 1..2 |-> "idle"]

Next == \/ /\ flag' = [flag EXCEPT ![1] = TRUE]
          /\ turn' = 2
          /\ state' = [state EXCEPT ![1] = "trying"]
        \/ /\ flag' = [flag EXCEPT ![2] = TRUE]
          /\ turn' = 1
          /\ state' = [state EXCEPT ![2] = "trying"]
        \/ /\ flag' = [flag EXCEPT ![1] = FALSE]
          /\ turn' = turn
          /\ state' = [state EXCEPT ![1] = "critical"]
        \/ /\ flag' = [flag EXCEPT ![2] = FALSE]
          /\ turn' = turn
          /\ state' = [state EXCEPT ![2] = "critical"]
        \/ /\ flag' = flag
          /\ turn' = turn
          /\ state' = [state EXCEPT ![1] = "idle"]
        \/ /\ flag' = flag
          /\ turn' = turn
          /\ state' = [state EXCEPT ![2] = "idle"]

Spec == Init /\ [][Next]_<<turn, flag, state>>

====
