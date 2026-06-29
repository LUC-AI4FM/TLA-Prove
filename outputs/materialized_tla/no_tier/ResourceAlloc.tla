---- MODULE ResourceAlloc ----
EXTENDS Integers, Sequences

CONSTANT N

VARIABLES owner, state

TypeOK == /\ owner \in 0..N \/ owner = 0
          /\ state \in {"idle", "acquired"}

Init == /\ owner = 0
        /\ state = "idle"

Request == /\ state = "idle"
          /\ owner' = 1
          /\ state' = "acquired"

Release == /\ state = "acquired"
           /\ owner' = 0
           /\ state' = "idle"

Next == \/ Request
        \/ Release

Spec == Init /\ [][Next]_<<owner, state>>

====
