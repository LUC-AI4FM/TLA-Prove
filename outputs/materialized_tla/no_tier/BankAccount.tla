---- MODULE BankAccount ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLE balance, deposit, withdraw

Init == /\ balance = 0
        /\ deposit = 0
        /\ withdraw = 0

Next == /\ balance' = balance + deposit - withdraw
        /\ deposit >= 0
        /\ withdraw >= 0
        /\ withdraw <= balance
        /\ deposit' = 0
        /\ withdraw' = 0

Spec == Init /\ [][Next]_<<balance, deposit, withdraw>>

TypeOK == /\ balance \in Int
          /\ deposit \in Int
          /\ withdraw \in Int

====
