---- MODULE BatchProc ----
EXTENDS Integers

CONSTANT Max

VARIABLES buf, processed

vars == <<buf, processed>>

Init == buf = 0 /\ processed = 0

Collect == buf < Max /\ buf' = buf + 1 /\ UNCHANGED processed

Flush == buf > 0 /\ processed < Max /\ processed' = processed + 1 /\ buf' = 0

Next == Collect \/ Flush \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == buf \in 0..Max /\ processed \in 0..Max

SafetyBounded == buf >= 0 /\ buf <= Max /\ processed >= 0 /\ processed <= Max
====
