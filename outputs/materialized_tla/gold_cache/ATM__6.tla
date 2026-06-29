---- MODULE ATM ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES state, card, pin, balance

(* State machine states *)
Idle == "Idle"
CardInserted == "CardInserted"
PINEntered == "PINEntered"
Dispensing == "Dispensing"
Done == "Done"

(* Initial state *)
Init == /\ state = Idle
        /\ card = {}
        /\ pin = {}
        /\ balance = 0

(* State transitions *)
Next == \/ /\ state = Idle
          /\ state' = CardInserted
          /\ card' = card
          /\ pin' = pin
          /\ balance' = balance
      \/ /\ state = CardInserted
          /\ state' = PINEntered
          /\ card' = card
          /\ pin' = pin
          /\ balance' = balance
      \/ /\ state = PINEntered
          /\ state' = Dispensing
          /\ card' = card
          /\ pin' = pin
          /\ balance' = balance
      \/ /\ state = Dispensing
          /\ state' = Done
          /\ card' = card
          /\ pin' = pin
          /\ balance' = balance
      \/ /\ state = Done
          /\ state' = Idle
          /\ card' = {}
          /\ pin' = {}
          /\ balance' = 0

Spec == Init /\ [][Next]_<<state, card, pin, balance>>

====
