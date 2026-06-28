---- MODULE BoundedFIFOQueue ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT K

VARIABLES q, head, tail, size

vars == <<q, head, tail, size>>

Init == /\ q = [i \in 1..K |-> 0]  \* Queue initialized with zeros
        /\ head = 1
        /\ tail = 1
        /\ size = 0

ProducerAction == /\ size < K
                  /\ q[tail] = 0
                  /\ q' = [q EXCEPT ![tail] = 1]
                  /\ tail' = IF tail = K THEN 1 ELSE tail + 1
                  /\ size' = size + 1
                  /\ head' = head
                  /\ q' \in [1..K -> {0,1}]

ConsumerAction == /\ size > 0
                  /\ q[head] = 1
                  /\ q' = [q EXCEPT ![head] = 0]
                  /\ head' = IF head = K THEN 1 ELSE head + 1
                  /\ size' = size - 1
                  /\ tail' = tail
                  /\ q' \in [1..K -> {0,1}]

Next == ProducerAction \/ ConsumerAction

Spec == Init /\ [][Next]_vars

TypeOK == /\ head \in 1..K
          /\ tail \in 1..K
          /\ size \in 0..K
          /\ q \in [1..K -> {0,1}]

====
