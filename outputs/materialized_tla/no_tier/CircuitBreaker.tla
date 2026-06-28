---- MODULE CircuitBreaker ----
EXTENDS Integers
CONSTANT Threshold
VARIABLES state, failures

Init == state = "Closed" /\ failures = 0

Success == state = "Closed"
           /\ failures' = 0 /\ UNCHANGED state

Failure == state = "Closed" /\ failures < Threshold
           /\ failures' = failures + 1
           /\ state' = IF failures + 1 >= Threshold THEN "Open" ELSE "Closed"

Trip == state = "Open"
        /\ state' = "HalfOpen" /\ UNCHANGED failures

HalfSuccess == state = "HalfOpen"
               /\ state' = "Closed" /\ failures' = 0

HalfFailure == state = "HalfOpen"
               /\ state' = "Open" /\ UNCHANGED failures

Next == Success \/ Failure \/ Trip \/ HalfSuccess \/ HalfFailure
        \/ UNCHANGED <<state, failures>>

Spec == Init /\ [][Next]_<<state, failures>>

TypeOK == state \in {"Closed", "Open", "HalfOpen"}
          /\ failures \in 0..Threshold

FailuresBounded == failures <= Threshold

SafetyInv == state = "Open" => failures >= Threshold
====
