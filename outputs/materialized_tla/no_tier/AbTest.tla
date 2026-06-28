---- MODULE AbTest ----
EXTENDS Integers

CONSTANT Max

VARIABLES groupA, groupB

vars == <<groupA, groupB>>

Init == groupA = 0 /\ groupB = 0

AssignA == groupA + groupB < Max /\ groupA' = groupA + 1 /\ UNCHANGED groupB

AssignB == groupA + groupB < Max /\ groupB' = groupB + 1 /\ UNCHANGED groupA

Next == AssignA \/ AssignB \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == groupA \in 0..Max /\ groupB \in 0..Max

SafetyBounded == groupA + groupB <= Max
====
