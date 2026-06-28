---- MODULE TicketDispenser ----
EXTENDS Integers, Sequences

CONSTANTS MAX

VARIABLES ticket, counter, state

TypeOK == /\ ticket \in 0..MAX
          /\ counter \in 0..MAX
          /\ state \in {"idle", "serving", "halted"}

Init == /\ ticket = 0
        /\ counter = 0
        /\ state = "idle"

Next == \/ /\ state = "idle"
            /\ ticket < MAX
            /\ ticket' = ticket + 1
            /\ counter' = counter
            /\ state' = "serving"
            /\ UNCHANGED <<counter>>
       \/ /\ state = "serving"
            /\ counter' = counter + 1
            /\ ticket' = ticket
            /\ state' = IF counter' = MAX THEN "halted" ELSE "serving"
       \/ /\ state = "halted"
            /\ UNCHANGED <<ticket, counter, state>>

Spec == Init /\ [][Next]_<<ticket, counter, state>>

====
