---- MODULE TicketDispenser ----
EXTENDS Integers, Sequences

CONSTANTS MAX

VARIABLES ticketNumber, counter

TypeOK == /\ ticketNumber \in 0..MAX
          /\ counter \in 0..MAX

Init == /\ ticketNumber = 0
        /\ counter = 0

Next == /\ ticketNumber' = IF ticketNumber < MAX THEN ticketNumber + 1 ELSE ticketNumber
        /\ counter' = IF counter < MAX THEN counter + 1 ELSE counter

Spec == Init /\ [][Next]_<<ticketNumber, counter>>

====
