---- MODULE TokenRing ----
EXTENDS Naturals, Sequences, TLC

CONSTANT N

VARIABLE token



Init == token \in 1..N

Next == 
  /\ token' \in 1..N
  /\ token' = IF token = N THEN 1 ELSE token + 1

Spec == Init /\ [][Next]_token

(* Type checking *)
TypeOK == token \in 1..N

====
