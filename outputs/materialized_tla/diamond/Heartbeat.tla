---- MODULE Heartbeat ----
EXTENDS Integers
CONSTANT Threshold
VARIABLES missedCount, nodeStatus

Init == missedCount = 0 /\ nodeStatus = "alive"

ReceiveHeartbeat == nodeStatus = "alive"
    /\ missedCount' = 0 /\ UNCHANGED nodeStatus

MissHeartbeat == nodeStatus = "alive" /\ missedCount < Threshold
    /\ missedCount' = missedCount + 1
    /\ nodeStatus' = IF missedCount + 1 >= Threshold THEN "dead" ELSE "alive"

Recover == nodeStatus = "dead"
    /\ nodeStatus' = "alive" /\ missedCount' = 0

Next == ReceiveHeartbeat \/ MissHeartbeat \/ Recover
        \/ UNCHANGED <<missedCount, nodeStatus>>

Spec == Init /\ [][Next]_<<missedCount, nodeStatus>>

TypeOK == missedCount \in 0..Threshold
          /\ nodeStatus \in {"alive", "dead"}

MissedBounded == missedCount <= Threshold

DeadMeansThreshold == nodeStatus = "dead" => missedCount >= Threshold
====
