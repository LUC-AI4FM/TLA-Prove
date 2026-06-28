---- MODULE DoublerReset ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT MAX

VARIABLE x

Init == x = 1

Next == \/ x' = 2 * x /\ 2 * x <= MAX
        \/ x' = 1

Spec == Init /\ [][Next]_<<x>>

====
