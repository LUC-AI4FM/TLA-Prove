---- MODULE Counter ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES counter

(* CONSTANTS *)
CONSTANT MAX

(* Type invariants *)
TypeOK == /\ counter \in Int
          /\ counter \in 0..MAX

(* Initial state *)
Init == /\ counter = 0

(* Next-state relation *)
Next == /\ counter' \in 0..MAX
        /\ counter' = IF counter < MAX THEN counter + 1 ELSE counter

(* Specification *)
Spec == Init /\ [][Next]_<<counter>>

====
