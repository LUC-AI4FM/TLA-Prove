---- MODULE HealthCheck ----
EXTENDS Integers

VARIABLES status, checks

vars == <<status, checks>>

Init == status = 2 /\ checks = 0

Degrade == status > 0 /\ status' = status - 1 /\ UNCHANGED checks

Recover == status < 2 /\ status' = status + 1 /\ UNCHANGED checks

Probe == checks < 3 /\ checks' = checks + 1 /\ UNCHANGED status

Next == Degrade \/ Recover \/ Probe \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == status \in {0, 1, 2} /\ checks \in 0..3

SafetyBounded == status >= 0 /\ status <= 2 /\ checks <= 3
====
