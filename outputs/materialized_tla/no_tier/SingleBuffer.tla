---- MODULE SingleBuffer ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES buf, prod, cons

TypeOK == /\ buf \in {"empty", 0..9}
          /\ prod \in {"empty", 0..9}
          /\ cons \in {"empty", 0..9}

Init == /\ buf = "empty"
        /\ prod = "empty"
        /\ cons = "empty"

Next == \/ /\ prod = "empty"
           /\ buf' = prod
           /\ prod' = "empty"
           /\ cons' = cons
       \/ /\ cons = "empty"
           /\ buf' = cons
           /\ cons' = "empty"
           /\ prod' = prod

Spec == Init /\ [][Next]_<<buf, prod, cons>>

====
