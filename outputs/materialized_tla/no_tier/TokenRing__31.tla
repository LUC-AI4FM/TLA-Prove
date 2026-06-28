---- MODULE TokenRing ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES token, inCS

TypeOK == /\ token \in 1..N
          /\ inCS \in 1..N

Init == /\ token = 1
        /\ inCS = 1

Next == /\ token' = IF token = N THEN 1 ELSE token + 1
        /\ inCS' = token

Spec == Init /\ [][Next]_<<token, inCS>>

====
