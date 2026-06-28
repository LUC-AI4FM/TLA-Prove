---- MODULE DekkersAlgorithm ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES turn, wants

Init == /\ turn \in {0,1}
        /\ wants \in [0..1 -> BOOLEAN]

Next == 
  \/ /\ wants[0] = FALSE
      /\ wants[1] = FALSE
      /\ turn' = turn
      /\ wants' = wants
  \/ /\ wants[0] = TRUE
      /\ wants[1] = FALSE
      /\ turn' = 1
      /\ wants' = [wants EXCEPT ![0] = FALSE]
  \/ /\ wants[0] = FALSE
      /\ wants[1] = TRUE
      /\ turn' = 0
      /\ wants' = [wants EXCEPT ![1] = FALSE]
  \/ /\ wants[0] = TRUE
      /\ wants[1] = TRUE
      /\ turn' = turn
      /\ wants' = wants

Spec == Init /\ [][Next]_<<turn, wants>>

====
