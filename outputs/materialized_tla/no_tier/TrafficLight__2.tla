---- MODULE TrafficLight ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES state, timer

Red == "Red"
Green == "Green"
Yellow == "Yellow"

States == {Red, Green, Yellow}

Init == /\ state = Red
        /\ timer = 0

Next == \/ /\ state = Red
            /\ timer' = timer + 1
            /\ timer' <= 10
            /\ state' = Red
        \/ /\ state = Green
            /\ timer' = timer + 1
            /\ timer' <= 5
            /\ state' = Green
        \/ /\ state = Yellow
            /\ timer' = timer + 1
            /\ timer' <= 2
            /\ state' = Yellow
        \/ /\ state = Red
            /\ timer = 10
            /\ state' = Green
            /\ timer' = 0
        \/ /\ state = Green
            /\ timer = 5
            /\ state' = Yellow
            /\ timer' = 0
        \/ /\ state = Yellow
            /\ timer = 2
            /\ state' = Red
            /\ timer' = 0

Spec == Init /\ [][Next]_<<state, timer>>

====
