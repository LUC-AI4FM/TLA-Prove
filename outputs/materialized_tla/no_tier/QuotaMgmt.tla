---- MODULE QuotaMgmt ----
EXTENDS Integers

CONSTANT Max

VARIABLES allocated, remaining

vars == <<allocated, remaining>>

Init == allocated = 0 /\ remaining = Max

Allocate == remaining > 0 /\ allocated' = allocated + 1 /\ remaining' = remaining - 1

Release == allocated > 0 /\ allocated' = allocated - 1 /\ remaining' = remaining + 1

Next == Allocate \/ Release \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == allocated \in 0..Max /\ remaining \in 0..Max

SafetyConserved == allocated + remaining = Max
====
