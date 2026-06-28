---- MODULE Door ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES doorState, doorLock, doorKey

DoorState == {"Open", "Closed", "Locked"}
DoorKey == {"Key", "NoKey"}

Init == /\ doorState \in DoorState
        /\ doorLock \in DoorKey
        /\ doorKey \in DoorKey
        /\ doorState = "Closed"
        /\ doorLock = "NoKey"
        /\ doorKey = "Key"

Next == /\ doorState' \in DoorState
        /\ doorLock' \in DoorKey
        /\ doorKey' \in DoorKey
        /\ doorState = "Closed" /\ doorLock = "NoKey" /\ doorKey = "Key" /\ doorState' = "Open" /\ doorLock' = doorLock /\ doorKey' = doorKey
        \/ /\ doorState = "Open" /\ doorLock = "NoKey" /\ doorKey = "Key" /\ doorState' = "Closed" /\ doorLock' = doorLock /\ doorKey' = doorKey
        \/ /\ doorState = "Closed" /\ doorLock = "NoKey" /\ doorKey = "Key" /\ doorState' = "Locked" /\ doorLock' = "Key" /\ doorKey' = doorKey
        \/ /\ doorState = "Locked" /\ doorLock = "Key" /\ doorKey = "Key" /\ doorState' = "Closed" /\ doorLock' = "NoKey" /\ doorKey' = doorKey
        \/ /\ doorState = "Closed" /\ doorLock = "NoKey" /\ doorKey = "NoKey" /\ doorState' = "Closed" /\ doorLock' = doorLock /\ doorKey' = doorKey
        \/ /\ doorState = "Closed" /\ doorLock = "Key" /\ doorKey = "NoKey" /\ doorState' = "Closed" /\ doorLock' = doorLock /\ doorKey' = doorKey

Spec == Init /\ [][Next]_<<doorState, doorLock, doorKey>>

====
