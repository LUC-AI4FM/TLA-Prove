---- MODULE TempController ----
EXTENDS Integers
CONSTANT Max
VARIABLES temp, mode

Init == temp = Max \div 2 /\ mode = "idle"

Heat == temp < Max
        /\ temp' = temp + 1
        /\ mode' = "heating"

Cool == temp > 0
        /\ temp' = temp - 1
        /\ mode' = "cooling"

Idle == mode' = "idle" /\ UNCHANGED temp

Next == Heat \/ Cool \/ Idle
        \/ UNCHANGED <<temp, mode>>

Spec == Init /\ [][Next]_<<temp, mode>>

TypeOK == temp \in 0..Max /\ mode \in {"heating", "cooling", "idle"}

TempBounded == temp >= 0 /\ temp <= Max

SafetyInv == temp >= 0 /\ temp <= Max
====
