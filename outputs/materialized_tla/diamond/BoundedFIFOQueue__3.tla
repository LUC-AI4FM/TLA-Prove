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

(* Producer action: blocks when full *)
Producer == 
    /\ size < K
    /\ q' = Append(q, 1)  (* Enqueue a dummy value *)
    /\ tail' = IF tail = K THEN 1 ELSE tail + 1
    /\ size' = size + 1
    /\ UNCHANGED head

(* Consumer action: blocks when empty *)
Consumer == 
    /\ size > 0
    /\ q' = Tail(q)  (* Dequeue *)
    /\ head' = IF head = K THEN 1 ELSE head + 1
    /\ size' = size - 1
    /\ UNCHANGED tail

(* Next-state relation *)
Next == Producer \/ Consumer

(* Specification *)
Spec == Init /\ [][Next]_<<q, head, tail, size>>

====
