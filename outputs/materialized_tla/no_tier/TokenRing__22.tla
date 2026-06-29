---- MODULE TokenRing ----
EXTENDS Naturals, FiniteSets

CONSTANT N

VARIABLE token

vars == << token >>

Init == token = 1

Next == /\ token' = IF token = N THEN 1 ELSE token + 1

Spec == Init /\ [][Next]_vars

TypeOK == token \in 1..N

====
