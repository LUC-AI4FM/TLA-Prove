---- MODULE EventuallyConsistentCounter ----
EXTENDS Naturals, TLC

VARIABLES counter, delta

Init == 
  /\ counter = 0
  /\ delta = 0

Next == 
  /\ counter' = counter + delta
  /\ delta' = 0

Spec == Init /\ [][Next]_<<counter, delta>>

TypeOK == 
  /\ counter \in Nat
  /\ delta \in Nat

====
