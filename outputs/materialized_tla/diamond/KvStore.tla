---- MODULE KvStore ----
EXTENDS Integers
CONSTANT Capacity
VARIABLES keyCount, lastOp

Init == keyCount = 0 /\ lastOp = "none"

Write == keyCount < Capacity
         /\ keyCount' = keyCount + 1 /\ lastOp' = "write"

Delete == keyCount > 0
          /\ keyCount' = keyCount - 1 /\ lastOp' = "delete"

Read == keyCount > 0
        /\ UNCHANGED keyCount /\ lastOp' = "read"

Next == Write \/ Delete \/ Read \/ UNCHANGED <<keyCount, lastOp>>

Spec == Init /\ [][Next]_<<keyCount, lastOp>>

TypeOK == keyCount \in 0..Capacity
          /\ lastOp \in {"none", "write", "delete", "read"}

NoOverflow == keyCount <= Capacity

SafetyInv == keyCount >= 0 /\ keyCount <= Capacity
====
