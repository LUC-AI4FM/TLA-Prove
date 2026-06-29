---- MODULE DekkersAlgorithm ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES turn, wants

Init == /\ turn = 0
        /\ wants = <<FALSE, FALSE>>

Next == \/ /\ wants[1] = FALSE
          /\ wants[2] = FALSE
          /\ turn' = 0
          /\ wants' = <<TRUE, FALSE>>
        \/ /\ wants[1] = FALSE
          /\ wants[2] = FALSE
          /\ turn' = 1
          /\ wants' = <<FALSE, TRUE>>
        \/ /\ wants[1] = TRUE
          /\ wants[2] = FALSE
          /\ turn' = 0
          /\ wants' = <<TRUE, FALSE>>
        \/ /\ wants[1] = FALSE
          /\ wants[2] = TRUE
          /\ turn' = 1
          /\ wants' = <<FALSE, TRUE>>
        \/ /\ wants[1] = TRUE
          /\ wants[2] = TRUE
          /\ turn' = turn
          /\ wants' = wants

TypeOK == /\ turn \in {0, 1}
          /\ wants \in {<<FALSE, FALSE>>, <<TRUE, FALSE>>, <<FALSE, TRUE>>, <<TRUE, TRUE>>}

Spec == Init /\ [][Next]_<<turn, wants>>

====
