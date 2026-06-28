---- MODULE TokenRing ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N
VARIABLES token


vars == <<token>>

Init == token = 1

Next == token' = %(token, N) + 1

Spec == Init /\ [][Next]_vars

TypeOK == /\ token \in 1..N
====
