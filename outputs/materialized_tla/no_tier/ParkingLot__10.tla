---- MODULE ParkingLot ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N

VARIABLES occupied, cars

(* TypeOK ensures occupied is a set of integers within 1..N and cars is a natural number *)
TypeOK == 
    /\ occupied \subseteq 1..N
    /\ cars \in Nat

(* Init: parking lot starts empty *)
Init == 
    /\ occupied = {}
    /\ cars = 0

(* Next: car enters or leaves *)
Next == 
    \/ (* Car enters *)
        /\ cars < N
        /\ cars' = cars + 1
        /\ occupied' = occupied \cup {cars + 1}
    \/ (* Car leaves *)
        /\ cars > 0
        /\ cars' = cars - 1
        /\ occupied' = occupied \ {cars}

Spec == Init /\ [][Next]_<<occupied, cars>>

====
