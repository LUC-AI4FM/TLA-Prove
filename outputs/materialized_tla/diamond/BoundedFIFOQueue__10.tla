---- MODULE BoundedFIFOQueue ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT K

VARIABLES q, head, tail, size

vars == <<q, head, tail, size>>

TypeOK == 
  /\ q \in Seq(1..K)
  /\ head \in 1..K
  /\ tail \in 1..K
  /\ size \in 0..K

Init == 
  /\ q = <<>>
  /\ head = 1
  /\ tail = 1
  /\ size = 0

ProducerAction == 
  /\ size < K
  /\ q' = Append(q, 1)  \* Enqueue 1
  /\ tail' = IF tail = K THEN 1 ELSE tail + 1
  /\ size' = size + 1
  /\ UNCHANGED <<head>>

ConsumerAction == 
  /\ size > 0
  /\ q' = Tail(q)  \* Dequeue
  /\ head' = IF head = K THEN 1 ELSE head + 1
  /\ size' = size - 1
  /\ UNCHANGED <<tail>>

Next == ProducerAction \/ ConsumerAction

Spec == Init /\ [][Next]_vars

====
