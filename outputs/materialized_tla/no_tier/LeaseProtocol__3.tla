---- MODULE LeaseProtocol ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES owner, leaseEnd

Init == 
    /\ owner = 0
    /\ leaseEnd = 0

Next == 
    \/ /\ owner' = 0
       /\ leaseEnd' = 0
    \/ /\ owner' = owner
       /\ leaseEnd' = leaseEnd
    \/ /\ owner' = 1
       /\ leaseEnd' = 10

Spec == Init /\ [][Next]_<<owner, leaseEnd>>

====
