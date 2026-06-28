---- MODULE Toggle ----
EXTENDS Naturals

VARIABLE state

Init == state = 0

ToggleState ==
    state' = 1 - state

Next == ToggleState

Spec == Init /\ [][Next]_state

TypeOK == state \in {0, 1}

====
