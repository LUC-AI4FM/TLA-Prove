---- MODULE DekkersAlgorithm ----
EXTENDS Integers, Sequences

VARIABLE turn, wants

Init == /\ turn \in {0, 1}
        /\ wants = <<FALSE, FALSE>>

Next == \/ /\ wants[1] = FALSE
          /\ wants[2] = FALSE
          /\ turn' = turn
          /\ wants' = wants
        \/ /\ wants[1] = TRUE
          /\ wants[2] = FALSE
          /\ turn' = 1
          /\ wants' = <<FALSE, FALSE>>
        \/ /\ wants[1] = FALSE
          /\ wants[2] = TRUE
          /\ turn' = 0
          /\ wants' = <<FALSE, FALSE>>
        \/ /\ wants[1] = TRUE
          /\ wants[2] = TRUE
          /\ turn' = turn
          /\ wants' = <<FALSE, FALSE>>

Spec == Init /\ [][Next]_<<turn, wants>>

TypeOK == /\ turn \in {0, 1}
          /\ wants \in {<<FALSE, FALSE>>, <<FALSE, TRUE>>, <<TRUE, FALSE>>, <<TRUE, TRUE>>}

====
