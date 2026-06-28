---- MODULE BoundedFIFOQueue ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT K

VARIABLES q, head, tail, size

(* Type invariants *)
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

(* Producer action: enqueue *)
Enqueue == 
    /\ size < K
    /\ head' = head
    /\ tail' = IF tail = K THEN 1 ELSE tail + 1
    /\ size' = size + 1
    /\ q' = Append(q, 1)  (* placeholder value *)

(* Consumer action: dequeue *)
Dequeue == 
    /\ size > 0
    /\ head' = IF head = K THEN 1 ELSE head + 1
    /\ tail' = tail
    /\ size' = size - 1
    /\ q' = Tail(q)

(* Next-state relation *)
Next == Enqueue \/ Dequeue

(* Specification *)
Spec == Init /\ [][Next]_<<q, head, tail, size>>

====
