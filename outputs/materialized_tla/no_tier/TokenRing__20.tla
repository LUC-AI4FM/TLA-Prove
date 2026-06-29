---- MODULE TokenRing ----
EXTENDS Naturals, FiniteSets

CONSTANT N

VARIABLE token


Init == token \in 1..N

Next == 
  /\ token' \in 1..N
  /\ token' = IF token = N THEN 1 ELSE token + 1

Spec == Init /\ [][Next]_token

TypeOK == token \in 1..N

====
