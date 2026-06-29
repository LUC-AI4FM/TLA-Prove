---- MODULE PacketRouter ----
EXTENDS Integers
CONSTANT Max
VARIABLE queue

vars == <<queue>>

Init == queue = 0

Enqueue == queue < Max /\ queue' = queue + 1
Dequeue == queue > 0 /\ queue' = queue - 1

Next == Enqueue \/ Dequeue \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == queue \in 0..Max
SafetyBounded == queue >= 0 /\ queue <= Max
====
