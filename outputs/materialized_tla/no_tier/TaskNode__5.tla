---- MODULE TaskNode ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES status, done

TypeOK == 
  /\ status \in {"Pending", "Running", "Done"}
  /\ done \in BOOLEAN

Init == 
  /\ status = "Pending"
  /\ done = FALSE

Next == 
  \/ /\ status = "Pending"
     /\ status' = "Running"
     /\ done' = FALSE
  \/ /\ status = "Running"
     /\ status' = "Done"
     /\ done' = TRUE
  \/ /\ status = "Done"
     /\ status' = "Done"
     /\ done' = TRUE

Spec == Init /\ [][Next]_<<status, done>>

====
