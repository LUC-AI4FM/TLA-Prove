---- MODULE DekkersAlgorithm ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES turn, wants

Init == /\ turn \in {1, 2}
        /\ wants \in {1, 2, 3}
        /\ turn = 1
        /\ wants = 1

Next == 
  /\ turn' \in {1, 2}
  /\ wants' \in {1, 2, 3}
  /\ (turn = 1 /\ wants = 1) => /\ turn' = 2
                                 /\ wants' = 2
  /\ (turn = 1 /\ wants = 2) => /\ turn' = 1
                                 /\ wants' = 3
  /\ (turn = 1 /\ wants = 3) => /\ turn' = 1
                                 /\ wants' = 3
  /\ (turn = 2 /\ wants = 1) => /\ turn' = 2
                                 /\ wants' = 1
  /\ (turn = 2 /\ wants = 2) => /\ turn' = 2
                                 /\ wants' = 3
  /\ (turn = 2 /\ wants = 3) => /\ turn' = 1
                                 /\ wants' = 3

Spec == Init /\ [][Next]_<<turn, wants>>

====
