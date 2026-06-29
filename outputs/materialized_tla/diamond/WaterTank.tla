---- MODULE WaterTank ----
EXTENDS Integers
CONSTANT Max
VARIABLE level

vars == <<level>>

Init == level = 0

Fill  == level < Max /\ level' = level + 1
Drain == level > 0 /\ level' = level - 1

Next == Fill \/ Drain \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == level \in 0..Max
SafetyBounded == level >= 0 /\ level <= Max
NoOverflow == level <= Max
NoUnderflow == level >= 0
====
