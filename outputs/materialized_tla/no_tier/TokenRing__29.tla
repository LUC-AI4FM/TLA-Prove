---- MODULE TokenRing ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N

VARIABLES token

vars == << token >>

Init == token \in 1..N

Next ==
  /\ token' = IF token = N THEN 1 ELSE token + 1

Spec == Init /\ [][Next]_vars

\* Invariant: token always in [1..N]
TypeOK == token \in 1..N
====
