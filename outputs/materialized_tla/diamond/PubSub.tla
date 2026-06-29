---- MODULE PubSub ----
EXTENDS Integers
CONSTANT Max
VARIABLES pending, consumed

vars == <<pending, consumed>>

Init == pending = 0 /\ consumed = 0

Publish   == /\ pending < Max
             /\ pending' = pending + 1
             /\ UNCHANGED consumed

Subscribe == /\ pending > 0
             /\ consumed < Max
             /\ pending' = pending - 1
             /\ consumed' = consumed + 1

Reset == /\ consumed > 0
         /\ consumed' = consumed - 1
         /\ UNCHANGED pending

Next == Publish \/ Subscribe \/ Reset \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == /\ pending \in 0..Max
          /\ consumed \in 0..Max
SafetyBounded == pending >= 0 /\ pending <= Max
SafetyValid == consumed >= 0 /\ consumed <= Max
====
