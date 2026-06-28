---- MODULE TrafficLight ----
EXTENDS Naturals, Sequences, FiniteSets

VARIABLES state, timer



TypeOK == /\ state \in {"Red", "Green", "Yellow"}
          /\ timer \in Nat

Init == /\ state = "Red"
        /\ timer = 60

Next == \/ /\ state = "Red"
              /\ state' = "Green"
              /\ timer' = 60
          \/ /\ state = "Green"
              /\ state' = "Yellow"
              /\ timer' = 5
          \/ /\ state = "Yellow"
              /\ state' = "Red"
              /\ timer' = 60
          \/ /\ state' = state
              /\ timer' = timer - 1
              /\ timer > 0

Spec == Init /\ [][Next]_<<state, timer>>

====
