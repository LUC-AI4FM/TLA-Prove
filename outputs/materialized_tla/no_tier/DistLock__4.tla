---- MODULE DistLock ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N, Nodes

VARIABLES lockHolder, waitingQueue

Init == /\ lockHolder = 0
        /\ waitingQueue = <<>>

Next == 
    \/ /\ lockHolder # 0
        /\ lockHolder' = 0
        /\ waitingQueue' = Append(waitingQueue, 0)
    \/ /\ lockHolder = 0
        /\ waitingQueue # <<>>
        /\ lockHolder' = Head(waitingQueue)
        /\ waitingQueue' = Tail(waitingQueue)
    \/ /\ lockHolder = 0
        /\ waitingQueue = <<>>
        /\ lockHolder' = 0
        /\ waitingQueue' = <<>>

Spec == Init /\ [][Next]_<<lockHolder, waitingQueue>>

====
