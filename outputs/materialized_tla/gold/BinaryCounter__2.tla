---- MODULE BinaryCounter ----
EXTENDS Integers, Sequences

VARIABLES x, y

Init == /\ x = 0
        /\ y = 0

Next == \/ /\ x = 0 /\ y = 0
              /\ x' = 1 /\ y' = 0
          \/ /\ x = 1 /\ y = 0
              /\ x' = 0 /\ y' = 1
          \/ /\ x = 0 /\ y = 1
              /\ x' = 1 /\ y' = 1
          \/ /\ x = 1 /\ y = 1
              /\ x' = 0 /\ y' = 0

Spec == Init /\ [][Next]_<<x, y>>

====
