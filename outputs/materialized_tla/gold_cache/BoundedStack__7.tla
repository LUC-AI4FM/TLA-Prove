---- MODULE BoundedStack ----
EXTENDS Naturals, Sequences

CONSTANTS N
VARIABLES stack, maxCap

Init == /\ stack = <<>>
        /\ maxCap \in 1..N
        /\ Len(stack) <= maxCap

Push == /\ Len(stack) < maxCap
        /\ stack' = Append(stack, 0)
        /\ maxCap' = maxCap

Pop == /\ Len(stack) > 0
       /\ stack' = SubSeq(stack, 1, Len(stack)-1)
       /\ maxCap' = maxCap

Next == Push \/ Pop

Spec == Init /\ [][Next]_<<stack, maxCap>>

TypeOK == /\ stack \in Seq(Nat)
          /\ maxCap \in Nat
          /\ Len(stack) <= maxCap

====
