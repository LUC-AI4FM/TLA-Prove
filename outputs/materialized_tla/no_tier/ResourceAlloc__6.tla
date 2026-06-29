---- MODULE ResourceAlloc ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES owner, waiting

Init == /\ owner = 0
        /\ waiting = <<>>

Next == \/ /\ owner = 0
              /\ waiting = <<>>
              /\ owner' = 0
                 /\ waiting' = <<>>
           \/ /\ owner = 0
              /\ Len(waiting) > 0
              /\ owner' = Head(waiting)
                 /\ waiting' = Tail(waiting)
           \/ /\ owner > 0
              /\ owner' = owner
                 /\ waiting' = waiting

Spec == Init /\ [][Next]_<<owner, waiting>>

====
