---- MODULE ParkingLot ----
EXTENDS Integers
CONSTANT Max
VARIABLES occupied, waiting

vars == <<occupied, waiting>>

Init == occupied = 0 /\ waiting = 0

Enter == /\ occupied < Max /\ waiting = 0
         /\ occupied' = occupied + 1
         /\ UNCHANGED waiting

QueueUp == /\ occupied = Max /\ waiting < Max
           /\ waiting' = waiting + 1
           /\ UNCHANGED occupied

Admit == /\ occupied < Max /\ waiting > 0
         /\ occupied' = occupied + 1
         /\ waiting' = waiting - 1

Exit == /\ occupied > 0
        /\ occupied' = occupied - 1
        /\ UNCHANGED waiting

Next == Enter \/ QueueUp \/ Admit \/ Exit \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == /\ occupied \in 0..Max
          /\ waiting \in 0..Max
SafetyBounded == occupied <= Max /\ waiting <= Max
SafetyValid == occupied >= 0 /\ waiting >= 0
====
