---- MODULE BoundedBuffer ----
EXTENDS Integers
CONSTANT BufSize
VARIABLE bufLen

Init == bufLen = 0

Produce == bufLen < BufSize /\ bufLen' = bufLen + 1

Consume == bufLen > 0 /\ bufLen' = bufLen - 1

Next == Produce \/ Consume \/ UNCHANGED bufLen

Spec == Init /\ [][Next]_bufLen

TypeOK == bufLen \in 0..BufSize

NoOverflow == bufLen <= BufSize
NoUnderflow == bufLen >= 0
SafetyInv == NoOverflow /\ NoUnderflow
====
