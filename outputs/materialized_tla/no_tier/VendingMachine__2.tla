---- MODULE VendingMachine ----
EXTENDS Integers
CONSTANT MaxBalance, InitStock
VARIABLES balance, stock, dispensed

Init == balance = 0 /\ stock = InitStock /\ dispensed = 0

InsertCoin == balance < MaxBalance
              /\ balance' = balance + 1
              /\ UNCHANGED <<stock, dispensed>>

Buy == balance >= 2 /\ stock > 0
       /\ balance' = balance - 2
       /\ stock' = stock - 1
       /\ dispensed' = dispensed + 1

Refund == balance > 0
          /\ balance' = 0
          /\ UNCHANGED <<stock, dispensed>>

Next == InsertCoin \/ Buy \/ Refund
        \/ UNCHANGED <<balance, stock, dispensed>>

Spec == Init /\ [][Next]_<<balance, stock, dispensed>>

TypeOK == balance \in 0..MaxBalance
          /\ stock \in 0..InitStock
          /\ dispensed \in 0..InitStock

StockConserved == stock + dispensed = InitStock

BalanceBounded == balance >= 0 /\ balance <= MaxBalance
====
