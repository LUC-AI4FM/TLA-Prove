---- MODULE VendingMachine ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES balance, inventory, selectedItem

Init == /\ balance = 0
        /\ inventory = [item \in {"Soda", "Chips", "Candy"} |-> 5]
        /\ selectedItem = ""

Next == \/ /\ balance = 0
          /\ selectedItem = ""
          /\ inventory = [item \in {"Soda", "Chips", "Candy"} |-> 5]
          /\ balance' = 0
          /\ inventory' = inventory
          /\ selectedItem' = selectedItem
        \/ /\ balance > 0
          /\ selectedItem # ""
          /\ inventory[selectedItem] > 0
          /\ balance >= 2
          /\ balance' = balance - 2
          /\ inventory' = [inventory EXCEPT ![selectedItem] = inventory[selectedItem] - 1]
          /\ selectedItem' = ""
        \/ /\ balance > 2
          /\ selectedItem # ""
          /\ inventory[selectedItem] > 0
          /\ balance >= 3
          /\ balance' = balance - 3
          /\ inventory' = [inventory EXCEPT ![selectedItem] = inventory[selectedItem] - 1]
          /\ selectedItem' = ""

Spec == Init /\ [][Next]_<<balance, inventory, selectedItem>>

====
