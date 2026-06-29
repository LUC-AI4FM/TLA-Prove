---- MODULE LightSwitch ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES state

Init == /\ state \in {"ON", "OFF"}

Next == \/ /\ state = "ON" /\ state' = "OFF"
      \/ /\ state = "OFF" /\ state' = "ON"

Spec == Init /\ [][Next]_<<state>>

====
