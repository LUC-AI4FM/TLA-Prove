---- MODULE Clock ----
EXTENDS Integers, Sequences

CONSTANT MAX

VARIABLES t

Init == t = 0

Next == t' = IF t = MAX THEN 0 ELSE t + 1

Spec == Init /\ [][Next]_t
====
