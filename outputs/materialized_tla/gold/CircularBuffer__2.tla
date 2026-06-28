---- MODULE CircularBuffer ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES buffer, readPtr, writePtr

Init == /\ buffer = [i \in 0..N-1 |-> 0]
        /\ readPtr = 0
        /\ writePtr = 0

Next == \/ \* Write operation
          /\ writePtr' = (writePtr + 1) % N
          /\ buffer' = [buffer EXCEPT ![writePtr] = 1]
          /\ readPtr' = readPtr
        \/ \* Read operation
          /\ readPtr' = (readPtr + 1) % N
          /\ buffer' = [buffer EXCEPT ![readPtr] = 0]
          /\ writePtr' = writePtr

Spec == Init /\ [][Next]_<<buffer, readPtr, writePtr>>

TypeOK == /\ buffer \in [0..N-1 -> {0,1}]
          /\ readPtr \in 0..N-1
          /\ writePtr \in 0..N-1

====
