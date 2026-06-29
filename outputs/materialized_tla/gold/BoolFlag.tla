---- MODULE BoolFlag ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES flag

Init == 
  /\ flag = FALSE

Next == 
  /\ flag' \in {TRUE, FALSE}
  /\ flag' = IF flag = FALSE THEN TRUE ELSE FALSE

Spec == Init /\ [][Next]_<<flag>>

====
