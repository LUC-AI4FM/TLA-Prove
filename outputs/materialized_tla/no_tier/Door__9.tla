---- MODULE Door ----
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS Door


VARIABLES state

(* State space: 0 = Open, 1 = Closed, 2 = Locked *)
Init == state = 0

Next ==
  \/ /\ state = 0
     /\ state' = 1  \* Close the door
  \/ /\ state = 1
     /\ state' = 2  \* Lock the door
  \/ /\ state = 2
     /\ state' = 1  \* Unlock the door

Spec == Init /\ [][Next]_state

====
