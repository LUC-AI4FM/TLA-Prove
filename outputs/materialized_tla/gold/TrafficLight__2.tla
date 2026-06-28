---- MODULE TrafficLight ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES state, timer

(* State can be "Red", "Green", or "Yellow" *)
State == {"Red", "Green", "Yellow"}

(* Timer counts down from a preset value for each state *)
Timer == 0 .. 100

(* Type invariant *)
TypeOK == state \in State /\ timer \in Timer

(* Initial state: Red with timer at 60 *)
Init == /\ state = "Red" /\ timer = 60

(* Next-state relation *)
Next ==
  \/ /\ state = "Red" /\ timer > 0
     /\ state' = "Red" /\ timer' = timer - 1
  \/ /\ state = "Red" /\ timer = 0
     /\ state' = "Green" /\ timer' = 30
  \/ /\ state = "Green" /\ timer > 0
     /\ state' = "Green" /\ timer' = timer - 1
  \/ /\ state = "Green" /\ timer = 0
     /\ state' = "Yellow" /\ timer' = 5
  \/ /\ state = "Yellow" /\ timer > 0
     /\ state' = "Yellow" /\ timer' = timer - 1
  \/ /\ state = "Yellow" /\ timer = 0
     /\ state' = "Red" /\ timer' = 60

Spec == Init /\ [][Next]_<<state, timer>>

====
