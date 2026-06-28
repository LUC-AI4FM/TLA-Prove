---- MODULE CanaryDeploy ----
EXTENDS Integers

CONSTANT Max

VARIABLES stable, canary

vars == <<stable, canary>>

Init == stable = Max /\ canary = 0

Shift == stable > 0 /\ stable' = stable - 1 /\ canary' = canary + 1

Rollback == canary > 0 /\ canary' = canary - 1 /\ stable' = stable + 1

Next == Shift \/ Rollback \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == stable \in 0..Max /\ canary \in 0..Max

SafetyConserved == stable + canary = Max
====
