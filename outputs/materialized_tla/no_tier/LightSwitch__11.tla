---- MODULE LightSwitch ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES state



Init == /\ state \in {"ON", "OFF"}
      /\ state = "OFF"

Next == /\ state' \in {"ON", "OFF"}
      /\ state' = IF state = "OFF" THEN "ON" ELSE "OFF"

Spec == Init /\ [][Next]_<<state>>

====
