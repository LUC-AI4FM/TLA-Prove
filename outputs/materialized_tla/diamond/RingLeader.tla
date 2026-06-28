---- MODULE RingLeader ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N, ID

VARIABLES leader, state

(* Type definitions *)
TypeOK == /\ leader \in 1..N
        /\ state \in 1..N

(* Initial state *)
Init == /\ leader = 1
       /\ state = 1

(* Next state action *)
Next == /\ state' = IF state = N THEN 1 ELSE state + 1
       /\ leader' = IF state = N THEN ID ELSE leader

Spec == Init /\ [][Next]_<<leader, state>>

====
