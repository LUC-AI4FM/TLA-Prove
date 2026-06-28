---- MODULE Toggle ----
EXTENDS Naturals, TLC

VARIABLES state

(*--@@
  The state variable can be either "ON" or "OFF".
--@@*)
TypeOK == state \in {"ON", "OFF"}

Init == state = "OFF"

Next == \/ state' = "ON" /\ state = "OFF"
        \/ state' = "OFF" /\ state = "ON"

Spec == Init /\ [][Next]_state

====
