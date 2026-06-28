---- MODULE SimpleChain ----
EXTENDS Integers
CONSTANT Max
VARIABLES pending, confirmed

vars == <<pending, confirmed>>

Init == pending = 0 /\ confirmed = 0

AddBlock == /\ pending + confirmed < Max
            /\ pending' = pending + 1
            /\ UNCHANGED confirmed

ConfirmBlock == /\ pending > 0
                /\ confirmed' = confirmed + 1
                /\ pending' = pending - 1

Next == AddBlock \/ ConfirmBlock \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == /\ pending \in 0..Max
          /\ confirmed \in 0..Max
          /\ pending + confirmed <= Max
SafetyBounded == pending + confirmed <= Max
SafetyValid == pending >= 0 /\ confirmed >= 0
====
