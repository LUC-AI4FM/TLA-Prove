---- MODULE          ATM ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES state, card, pin, dispensed


(* BEGIN
  state == "Idle";
  card == "None";
  pin == "None";
  dispensed == 0;

  (* --state Idle --*)
  state == "Idle" => 
    (* --action InsertCard --*)
    card' == "Inserted" /\ pin' == "None" /\ dispensed' == 0 /\ state' == "CardInserted";
  (* --state CardInserted --*)
  state == "CardInserted" => 
    (* --action EnterPIN --*)
    pin' == "Entered" /\ dispensed' == 0 /\ state' == "PINEntered";
  (* --state PINEntered --*)
  state == "PINEntered" => 
    (* --action DispenseCash --*)
    dispensed' == 100 /\ state' == "Dispensing";
  (* --state Dispensing --*)
  state == "Dispensing" => 
    (* --action Finish --*)
    dispensed' == 0 /\ state' == "Done";
  (* --state Done --*)
  state == "Done" => 
    (* --action Reset --*)
    card' == "None" /\ pin' == "None" /\ dispensed' == 0 /\ state' == "Idle";
  (* --state --*)
  state' == state /\ card' == card /\ pin' == pin /\ dispensed' == dispensed;
END *)

(* --state machine --*)
Init == 
  /\ state = "Idle"
  /\ card = "None"
  /\ pin = "None"
  /\ dispensed = 0

Next == 
  (* --action InsertCard --*)
  /\ state' = "CardInserted"
  /\ card' = "Inserted"
  /\ pin' = "None"
  /\ dispensed' = 0
  /\ state = "Idle"

  \/ (* --action EnterPIN --*)
  /\ state' = "PINEntered"
  /\ card' = card
  /\ pin' = "Entered"
  /\ dispensed' = 0
  /\ state = "CardInserted"

  \/ (* --action DispenseCash --*)
  /\ state' = "Dispensing"
  /\ card' = card
  /\ pin' = pin
  /\ dispensed' = 100
  /\ state = "PINEntered"

  \/ (* --action Finish --*)
  /\ state' = "Done"
  /\ card' = card
  /\ pin' = pin
  /\ dispensed' = 0
  /\ state = "Dispensing"

  \/ (* --action Reset --*)
  /\ state' = "Idle"
  /\ card' = "None"
  /\ pin' = "None"
  /\ dispensed' = 0
  /\ state = "Done"

  \/ (* --action NoChange --*)
  /\ state' = state
  /\ card' = card
  /\ pin' = pin
  /\ dispensed' = dispensed

Spec == Init /\ [][Next]_<<state, card, pin, dispensed>>

====
