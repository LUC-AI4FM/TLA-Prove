---- MODULE BoundedFIFO ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N
VARIABLES q, head, tail

Init == /\ q = <<>>
        /\ head = 0
        /\ tail = 0

Next == \/ /\ head < tail
          /\ q' = Append(q, [x \in 1..N |-> head + 1])
          /\ head' = head + 1
          /\ tail' = tail
        \/ /\ head = tail
          /\ q' = <<>>
          /\ head' = 0
          /\ tail' = 0

Spec == Init /\ [][Next]_<<q, head, tail>>

====
