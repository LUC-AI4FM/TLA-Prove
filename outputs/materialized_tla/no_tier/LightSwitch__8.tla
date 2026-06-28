---- MODULE LightSwitch ----
EXTENDS Naturals

VARIABLE light

Init == light = 0

Toggle == light' = 1 - light

Next == Toggle

Spec == Init /\ [][Next]_light

TypeOK == light \in {0, 1}

====
