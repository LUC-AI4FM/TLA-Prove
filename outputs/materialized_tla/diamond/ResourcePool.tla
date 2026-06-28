---- MODULE ResourcePool ----
EXTENDS Integers
CONSTANT N
VARIABLES available, inUse

Init == available = N /\ inUse = 0

Checkout == available > 0
            /\ available' = available - 1 /\ inUse' = inUse + 1

Return == inUse > 0
          /\ inUse' = inUse - 1 /\ available' = available + 1

Next == Checkout \/ Return \/ UNCHANGED <<available, inUse>>

Spec == Init /\ [][Next]_<<available, inUse>>

TypeOK == available \in 0..N /\ inUse \in 0..N

ResourceConserved == available + inUse = N

SafetyInv == available >= 0 /\ inUse >= 0
====
