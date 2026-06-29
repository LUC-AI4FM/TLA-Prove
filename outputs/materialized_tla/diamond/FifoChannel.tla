---- MODULE FifoChannel ----
EXTENDS Integers
CONSTANT Capacity
VARIABLES chanLen, nextId

Init == chanLen = 0 /\ nextId = 1

Send == chanLen < Capacity /\ nextId < Capacity * 2
        /\ chanLen' = chanLen + 1 /\ nextId' = nextId + 1

Receive == chanLen > 0
           /\ chanLen' = chanLen - 1 /\ UNCHANGED nextId

Next == Send \/ Receive \/ UNCHANGED <<chanLen, nextId>>

Spec == Init /\ [][Next]_<<chanLen, nextId>>

TypeOK == chanLen \in 0..Capacity /\ nextId \in 1..(Capacity * 2)

NoOverflow == chanLen <= Capacity

SafetyInv == chanLen >= 0 /\ chanLen <= Capacity
====
