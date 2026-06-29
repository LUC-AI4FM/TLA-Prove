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

(* Initial state *)
Init == 
    /\ q = <<>>
    /\ head = 1
    /\ tail = 1
    /\ size = 0

(* Producer action: enqueue *)
Enqueue == 
    /\ size < K
    /\ q' = Append(q, 1)  (* placeholder value *)
    /\ head' = head
    /\ tail' = IF tail = K THEN 1 ELSE tail + 1
    /\ size' = size + 1

(* Consumer action: dequeue *)
Dequeue == 
    /\ size > 0
    /\ q' = Tail(q)
    /\ head' = IF head = K THEN 1 ELSE head + 1
    /\ tail' = tail
    /\ size' = size - 1

(* Next-state relation *)
Next == Enqueue \/ Dequeue

(* Specification *)
Spec == Init /\ [][Next]_<<q, head, tail, size>>

====
