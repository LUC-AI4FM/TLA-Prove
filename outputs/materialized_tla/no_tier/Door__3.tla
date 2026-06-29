---- MODULE Door ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES doorState, doorLock

(* --type definitions-- *)
DoorState == {"Open", "Closed", "Locked"}
DoorLock == {"Unlocked", "Locked"}

(* --initialization-- *)
Init == /\ doorState \in DoorState
        /\ doorLock \in DoorLock
        /\ doorState = "Closed"
        /\ doorLock = "Unlocked"

(* --next-state relation-- *)
Next == \/ /\ doorState = "Closed"
          /\ doorLock = "Unlocked"
          /\ doorState' = "Open"
          /\ doorLock' = doorLock
        \/ /\ doorState = "Open"
          /\ doorLock' = doorLock
          /\ doorState' = "Closed"
        \/ /\ doorState = "Closed"
          /\ doorLock = "Unlocked"
          /\ doorState' = "Closed"
          /\ doorLock' = "Locked"
        \/ /\ doorState = "Closed"
          /\ doorLock = "Locked"
          /\ doorState' = "Closed"
          /\ doorLock' = "Unlocked"

(* --specification-- *)
Spec == Init /\ [][Next]_<<doorState, doorLock>>

====
