---- MODULE BoundedFIFO ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES q, sz

Init == /\ q = << >>
       /\ sz = 0

Next == \E x \in 1..N :
          \/ /\ sz < N
             /\ q' = Append(q, x)
             /\ sz' = sz + 1
          \/ /\ sz > 0
             /\ q' = Tail(q)
             /\ sz' = sz - 1

Spec == Init /\ [][Next]_<<q, sz>>

====
