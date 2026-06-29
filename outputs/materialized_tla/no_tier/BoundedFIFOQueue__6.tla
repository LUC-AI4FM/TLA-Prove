---- MODULE BoundedFIFOQueue ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT K

VARIABLES q, head, tail, size

(* Type invariant *)
TypeOK == 
    /\ q \in Seq(1..K)
    /\ head \in 1..K
    /\ tail \in 1..K
    /\ size \in 0..K

(* Initial state: empty queue *)
Init == 
    /\ q = <<>>
    /\ head = 1
    /\ tail = 1
    /\ size = 0

(* Producer action: enqueue an element e *)
Enqueue(e) == 
    /\ size < K
    /\ q' = Append(q, e)
    /\ head' = head
    /\ tail' = IF tail = K THEN 1 ELSE tail + 1
    /\ size' = size + 1

(* Consumer action: dequeue an element *)
Dequeue == 
    /\ size > 0
    /\ q' = Tail(q)
    /\ head' = IF head = K THEN 1 ELSE head + 1
    /\ tail' = tail
    /\ size' = size - 1

(* Next-state relation: either enqueue or dequeue *)
Next == 
    \E e \in 1..K : Enqueue(e) \/ Dequeue

Spec == Init /\ [][Next]_<<q, head, tail, size>>

====
