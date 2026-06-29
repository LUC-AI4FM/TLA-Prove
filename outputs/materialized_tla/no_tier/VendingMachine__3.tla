---- MODULE VendingMachine ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES balance, inventory

Init == /\ balance = 0
      /\ inventory = <<>>

Next == /\ UNCHANGED <<balance, inventory>>

Spec == Init /\ [][Next]_<<balance, inventory>>
====
