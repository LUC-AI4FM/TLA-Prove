---- MODULE CircularBuffer ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES buffer, readPtr, writePtr

TypeOK ==
  /\ buffer \in [1..N -> 0..1]
  /\ readPtr \in 1..N
  /\ writePtr \in 1..N

Init ==
  /\ buffer = [i \in 1..N |-> 0]
  /\ readPtr = 1
  /\ writePtr = 1

Write ==
  /\ buffer[writePtr] = 0
  /\ buffer' = [buffer EXCEPT ![writePtr] = 1]
  /\ writePtr' = IF writePtr = N THEN 1 ELSE writePtr + 1
  /\ readPtr' = readPtr

Read ==
  /\ buffer[readPtr] = 1
  /\ buffer' = [buffer EXCEPT ![readPtr] = 0]
  /\ readPtr' = IF readPtr = N THEN 1 ELSE readPtr + 1
  /\ writePtr' = writePtr

Next ==
  \/ Write
  \/ Read

Spec == Init /\ [][Next]_<<buffer, readPtr, writePtr>>

====
