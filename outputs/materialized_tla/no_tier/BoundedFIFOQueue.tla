---- MODULE BoundedFIFOQueue ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT K

VARIABLES q, head, tail, size

vars == <<q, head, tail, size>>

Init == 
    /\ q = [i \in 1..K |-> 0]  \* Queue initialized with zeros
    /\ head = 1
    /\ tail = 1
    /\ size = 0

ProducerAction == 
    /\ size < K
    /\ head' = head
    /\ tail' = (tail % K) + 1
    /\ size' = size + 1
    /\ q' = [q EXCEPT ![head] = 1]  \* Mark slot as occupied

ConsumerAction == 
    /\ size > 0
    /\ head' = (head % K) + 1
    /\ tail' = tail
    /\ size' = size - 1
    /\ q' = [q EXCEPT ![head] = 0]  \* Mark slot as free

Next == 
    \/ ProducerAction
    \/ ConsumerAction

Spec == Init /\ [][Next]_vars

TypeOK == 
    /\ head \in 1..K
    /\ tail \in 1..K
    /\ size \in 0..K
    /\ q \in [1..K -> {0,1}]

====
