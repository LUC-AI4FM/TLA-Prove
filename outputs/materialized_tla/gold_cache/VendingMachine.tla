---- MODULE VendingMachine ----
EXTENDS Integers, Sequences

CONSTANTS ItemPrice, MaxCoins


VARIABLES balance, insertedCoins, state

TypeOK == /\ balance \in 0..ItemPrice
          /\ insertedCoins \in 0..MaxCoins
          /\ state \in {"idle", "dispensing", "out_of_order"}
          /\ state = "idle" => balance < ItemPrice
          /\ state = "dispensing" => balance = ItemPrice

Init == /\ balance = 0
        /\ insertedCoins = 0
        /\ state = "idle"

InsertCoin == /\ state = "idle"
              /\ insertedCoins < MaxCoins
              /\ insertedCoins' = insertedCoins + 1
              /\ balance' = balance + 1
              /\ state' = IF balance' >= ItemPrice THEN "dispensing" ELSE "idle"

Dispense == /\ state = "dispensing"
            /\ balance' = 0
            /\ insertedCoins' = 0
            /\ state' = "idle"

Next == InsertCoin \/ Dispense

Spec == Init /\ [][Next]_<<balance, insertedCoins, state>>

====
