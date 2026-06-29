---- MODULE RaftLog ----
EXTENDS Integers
CONSTANT Max
VARIABLES leaderLog, followerLog, commitIdx

vars == <<leaderLog, followerLog, commitIdx>>

Init == leaderLog = 0 /\ followerLog = 0 /\ commitIdx = 0

AppendEntry == /\ leaderLog < Max
               /\ leaderLog' = leaderLog + 1
               /\ UNCHANGED <<followerLog, commitIdx>>

Replicate == /\ followerLog < leaderLog
             /\ followerLog' = followerLog + 1
             /\ UNCHANGED <<leaderLog, commitIdx>>

Commit == /\ commitIdx < followerLog
          /\ commitIdx' = commitIdx + 1
          /\ UNCHANGED <<leaderLog, followerLog>>

Next == AppendEntry \/ Replicate \/ Commit \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == /\ leaderLog \in 0..Max
          /\ followerLog \in 0..Max
          /\ commitIdx \in 0..Max
SafetyValid == /\ followerLog <= leaderLog
               /\ commitIdx <= followerLog
SafetyBounded == leaderLog <= Max
====
