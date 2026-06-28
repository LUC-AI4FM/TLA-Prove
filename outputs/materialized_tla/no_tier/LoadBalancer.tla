---- MODULE LoadBalancer ----
EXTENDS Integers
CONSTANT N
VARIABLES current, dispatched

vars == <<current, dispatched>>

Init == current = 0 /\ dispatched = 0

Dispatch == /\ dispatched < N * N
            /\ current' = (current + 1) % N
            /\ dispatched' = dispatched + 1

Next == Dispatch \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == /\ current \in 0..(N-1)
          /\ dispatched \in 0..(N*N)
SafetyBounded == dispatched <= N * N
SafetyValid == current >= 0 /\ current < N
====
