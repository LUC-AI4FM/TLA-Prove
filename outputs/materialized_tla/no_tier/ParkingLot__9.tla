---- MODULE ParkingLot ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES spaces, cars

(* Constants *)
N == 10

(* Type invariants *)
TypeOK == /\ spaces \in 0..N
          /\ cars \in 0..N
          /\ spaces + cars = N

(* Initial state *)
Init == /\ spaces = N
        /\ cars = 0

(* Next-state relation *)
Next == /\ spaces' = spaces - 1
        /\ cars' = cars + 1
        /\ spaces > 0
        \/ /\ spaces' = spaces + 1
           /\ cars' = cars - 1
           /\ cars > 0

Spec == Init /\ [][Next]_<<spaces, cars>>

====
