---- MODULE LeaseProtocol ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N, T

VARIABLES owner, lease, time, state

TypeOK == /\ owner \in 1..N
          /\ lease \in 1..N
          /\ time \in 0..T
          /\ state \in {"idle", "acquiring", "holding"}

Init == /\ owner = 1
        /\ lease = 1
        /\ time = 0
        /\ state = "idle"

Acquire == /\ state = "idle"
           /\ state' = "acquiring"
           /\ UNCHANGED <<owner, lease, time>>

Hold == /\ state = "acquiring"
        /\ state' = "holding"
        /\ UNCHANGED <<owner, lease, time>>

Release == /\ state = "holding"
           /\ state' = "idle"
           /\ UNCHANGED <<owner, lease, time>>

Next == \/ Acquire
        \/ Hold
        \/ Release

Spec == Init /\ [][Next]_<<owner, lease, time, state>>
====
