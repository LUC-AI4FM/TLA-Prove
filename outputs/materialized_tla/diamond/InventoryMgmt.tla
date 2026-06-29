---- MODULE InventoryMgmt ----
EXTENDS Integers

CONSTANT Max

VARIABLE stock

vars == <<stock>>

Init == stock = 0

Restock == stock < Max /\ stock' = stock + 1

Sell == stock > 0 /\ stock' = stock - 1

Next == Restock \/ Sell \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == stock \in 0..Max

SafetyBounded == stock >= 0 /\ stock <= Max
====
