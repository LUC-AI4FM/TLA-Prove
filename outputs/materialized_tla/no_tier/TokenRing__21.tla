---- MODULE TokenRing ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLE token

Init == token \in 1..N

Next == token' = IF token = N THEN 1 ELSE token + 1

Spec == Init /\ [][Next]_<<token>>

TypeOK == token \in 1..N

====
