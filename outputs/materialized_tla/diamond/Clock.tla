---- MODULE Clock ----
EXTENDS Integers
VARIABLES hours, minutes

Init == hours = 12 /\ minutes = 0

Tick ==
    /\ minutes' = IF minutes = 59 THEN 0 ELSE minutes + 1
    /\ hours' = IF minutes = 59
                THEN (IF hours = 12 THEN 1 ELSE hours + 1)
                ELSE hours

Next == Tick \/ UNCHANGED <<hours, minutes>>

Spec == Init /\ [][Next]_<<hours, minutes>>

TypeOK == hours \in 1..12 /\ minutes \in 0..59

HoursValid == hours >= 1 /\ hours <= 12
MinutesValid == minutes >= 0 /\ minutes < 60
====
