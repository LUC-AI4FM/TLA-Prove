---- MODULE ReadersWriters ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLE readers, writer

Init == /\ readers = 0
       /\ writer = FALSE

AcquireReader == /\ readers < N
                 /\ readers' = readers + 1
                 /\ writer' = writer

ReleaseReader == /\ readers > 0
                 /\ readers' = readers - 1
                 /\ writer' = writer

AcquireWriter == /\ readers = 0
                 /\ writer = FALSE
                 /\ writer' = TRUE
                 /\ readers' = readers

ReleaseWriter == /\ writer = TRUE
                 /\ writer' = FALSE
                 /\ readers' = readers

Next == \/ AcquireReader
        \/ ReleaseReader
        \/ AcquireWriter
        \/ ReleaseWriter

TypeOK == /\ readers \in 0..N
         /\ writer \in BOOLEAN

Spec == Init /\ [][Next]_<<readers, writer>> /\ TypeOK

====
