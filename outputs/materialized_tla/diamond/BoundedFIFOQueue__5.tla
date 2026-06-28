---- MODULE BoundedFIFOQueue ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT K

VARIABLES q, head, tail

vars == <<q, head, tail>>

Init == /\ q = [i \in 1..K |-> 0]
        /\ head = 1
        /\ tail = 1

TypeOK == /\ q \in [1..K -> Nat]
          /\ head \in 1..K
          /\ tail \in 1..K

Next == 
  \* Producer action: enqueue a value if the queue is not full
  \/ /\ head # tail
     /\ q' = [q EXCEPT ![head] = 1]
     /\ head' = IF head = K THEN 1 ELSE head + 1
     /\ tail' = tail
  \* Consumer action: dequeue a value if the queue is not empty
  \/ /\ head = tail
     /\ q' = [q EXCEPT ![head] = 0]
     /\ head' = head
     /\ tail' = IF tail = K THEN 1 ELSE tail + 1

Spec == Init /\ [][Next]_vars

====
