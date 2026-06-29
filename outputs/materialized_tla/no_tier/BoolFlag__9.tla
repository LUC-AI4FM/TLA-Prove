---- MODULE BoolFlag ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLE flag

Init == /\ flag \in {TRUE, FALSE}

Next == /\ flag' \in {TRUE, FALSE}
      /\ flag' # flag

Spec == Init /\ [][Next]_<<flag>>

====
