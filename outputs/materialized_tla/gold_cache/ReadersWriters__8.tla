---- MODULE ReadersWriters ----
EXTENDS Integers, Sequences

CONSTANTS N

VARIABLE readers, writer

TypeOK == /\ readers \in 0..N
          /\ writer \in BOOLEAN

Init == /\ readers = 0
        /\ writer = FALSE

Next == \/ /\ readers' = readers + 1
          /\ writer' = writer
          /\ readers < N
        \/ /\ readers' = readers
          /\ writer' = FALSE
          /\ readers > 0
        \/ /\ readers' = readers
          /\ writer' = TRUE
          /\ readers = 0
          /\ writer = FALSE

Spec == Init /\ [][Next]_<<readers, writer>>

====
