---- MODULE Barrier ----
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANT N

VARIABLES barrier, arrived

(* barrier: 0 = not released, 1 = released
   arrived: set of processes that have reached the barrier *)

Init == /\ barrier = 0
        /\ arrived = {}

Next ==
  \/ \E p \in 1..N :
        /\ ~(p \in arrived)
        /\ arrived' = arrived \cup {p}
        /\ barrier' = IF (arrived' = 1..N) THEN 1 ELSE barrier
  \/ barrier = 1 /\ barrier' = 1 /\ arrived' = arrived

Spec == Init /\ [][Next]_<<barrier, arrived>>

====
