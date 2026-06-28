---- MODULE Register ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLE value

Init == value = 0

Next == \/ value' = value
      \/ value' = 0

Spec == Init /\ [][Next]_<<value>> ====
