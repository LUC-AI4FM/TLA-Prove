---- MODULE BoundedStack ----
EXTENDS Integers, Sequences

CONSTANT N
ASSUME N \in Nat

VARIABLES stack, top

TypeOK == /\ stack \in Seq(1..N)
          /\ top \in 0..N
          /\ Len(stack) = top

Init == /\ stack = <<>>
        /\ top = 0

Push(x) == /\ top < N
           /\ stack' = Append(stack, x)
           /\ top' = top + 1
           /\ UNCHANGED <<top>>

Pop == /\ top > 0
       /\ stack' = SubSeq(stack, 1, top - 1)
       /\ top' = top - 1
       /\ UNCHANGED <<top>>

Next == \/ Push(1)
        \/ Pop
        \/ UNCHANGED <<stack, top>>

Spec == Init /\ [][Next]_<<stack, top>>

====
