---- MODULE ATM ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES state, cardInserted, pinEntered, dispensing, done

Init == /\ state = "Idle"
        /\ cardInserted = FALSE
        /\ pinEntered = FALSE
        /\ dispensing = FALSE
        /\ done = FALSE

Next == \/ /\ state = "Idle"
          /\ cardInserted = FALSE
          /\ pinEntered = FALSE
          /\ dispensing = FALSE
          /\ done = FALSE
          /\ state' = "CardInserted"
          /\ cardInserted' = TRUE
          /\ pinEntered' = FALSE
          /\ dispensing' = FALSE
          /\ done' = FALSE
        \/ /\ state = "CardInserted"
          /\ cardInserted = TRUE
          /\ pinEntered = FALSE
          /\ dispensing = FALSE
          /\ done = FALSE
          /\ state' = "PINEntered"
          /\ cardInserted' = TRUE
          /\ pinEntered' = TRUE
          /\ dispensing' = FALSE
          /\ done' = FALSE
        \/ /\ state = "PINEntered"
          /\ cardInserted = TRUE
          /\ pinEntered = TRUE
          /\ dispensing = FALSE
          /\ done = FALSE
          /\ state' = "Dispensing"
          /\ cardInserted' = TRUE
          /\ pinEntered' = TRUE
          /\ dispensing' = TRUE
          /\ done' = FALSE
        \/ /\ state = "Dispensing"
          /\ cardInserted = TRUE
          /\ pinEntered = TRUE
          /\ dispensing = TRUE
          /\ done = FALSE
          /\ state' = "Done"
          /\ cardInserted' = FALSE
          /\ pinEntered' = FALSE
          /\ dispensing' = FALSE
          /\ done' = TRUE
        \/ /\ state = "Done"
          /\ cardInserted = FALSE
          /\ pinEntered = FALSE
          /\ dispensing = FALSE
          /\ done = TRUE
          /\ state' = "Idle"
          /\ cardInserted' = FALSE
          /\ pinEntered' = FALSE
          /\ dispensing' = FALSE
          /\ done' = FALSE

Spec == Init /\ [][Next]_<<state, cardInserted, pinEntered, dispensing, done>>

====
