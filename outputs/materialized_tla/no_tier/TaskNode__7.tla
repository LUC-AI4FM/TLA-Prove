---- MODULE TaskNode ----
EXTENDS Naturals, TLC

VARIABLE status

Pending == status = "Pending"
Running == status = "Running"
Done == status = "Done"

Init == status = "Pending"

Next == 
   \/ Pending /\ status' = "Running"
   \/ Running /\ status' = "Done"
   \/ Done /\ UNCHANGED status

TypeOK == status \in {"Pending", "Running", "Done"}

Spec == Init /\ [][Next]_status

====
