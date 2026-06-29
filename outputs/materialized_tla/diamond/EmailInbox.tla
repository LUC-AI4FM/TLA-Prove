---- MODULE EmailInbox ----
EXTENDS Integers
CONSTANT Max
VARIABLES unread, read

vars == <<unread, read>>

Init == unread = 0 /\ read = 0

Receive    == /\ unread + read < Max
              /\ unread' = unread + 1
              /\ UNCHANGED read

ReadMsg    == /\ unread > 0
              /\ unread' = unread - 1
              /\ read' = read + 1

DeleteRead == /\ read > 0
              /\ read' = read - 1
              /\ UNCHANGED unread

Next == Receive \/ ReadMsg \/ DeleteRead \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == /\ unread \in 0..Max
          /\ read \in 0..Max
          /\ unread + read <= Max
SafetyBounded == unread + read <= Max
SafetyValid == unread >= 0 /\ read >= 0
====
