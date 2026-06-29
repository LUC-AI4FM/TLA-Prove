---- MODULE ParkingLot ----
EXTENDS Naturals

CONSTANTS N

VARIABLE occupied

Init == occupied = 0

Enter == occupied < N /\ occupied' = occupied + 1

Leave == occupied > 0 /\ occupied' = occupied - 1

Next == Enter \/ Leave

Spec == Init /\ [][Next]_occupied

TypeOK == occupied \in 0..N

====
