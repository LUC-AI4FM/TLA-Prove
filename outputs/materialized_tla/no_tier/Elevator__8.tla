---- MODULE Elevator ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES currentFloor, direction, requests

Init ==
    /\ currentFloor = 1
    /\ direction = 1
    /\ requests = {}

Next ==
    \/ /\ currentFloor \in 1..N
       /\ direction = 1
       /\ currentFloor < N
       /\ requests = {}
       /\ currentFloor' = currentFloor + 1
       /\ direction' = direction
       /\ requests' = requests
    \/ /\ currentFloor \in 1..N
       /\ direction = 1
       /\ currentFloor < N
       /\ requests # {}
       /\ currentFloor' = currentFloor
       /\ direction' = direction
       /\ requests' = requests \ {currentFloor}
    \/ /\ currentFloor \in 1..N
       /\ direction = 1
       /\ currentFloor = N
       /\ requests = {}
       /\ currentFloor' = currentFloor
       /\ direction' = -1
       /\ requests' = requests
    \/ /\ currentFloor \in 1..N
       /\ direction = 1
       /\ currentFloor = N
       /\ requests # {}
       /\ currentFloor' = currentFloor
       /\ direction' = direction
       /\ requests' = requests \ {currentFloor}
    \/ /\ currentFloor \in 1..N
       /\ direction = -1
       /\ currentFloor > 1
       /\ requests = {}
       /\ currentFloor' = currentFloor - 1
       /\ direction' = direction
       /\ requests' = requests
    \/ /\ currentFloor \in 1..N
       /\ direction = -1
       /\ currentFloor > 1
       /\ requests # {}
       /\ currentFloor' = currentFloor
       /\ direction' = direction
       /\ requests' = requests \ {currentFloor}
    \/ /\ currentFloor \in 1..N
       /\ direction = -1
       /\ currentFloor = 1
       /\ requests = {}
       /\ currentFloor' = currentFloor
       /\ direction' = 1
       /\ requests' = requests
    \/ /\ currentFloor \in 1..N
       /\ direction = -1
       /\ currentFloor = 1
       /\ requests # {}
       /\ currentFloor' = currentFloor
       /\ direction' = direction
       /\ requests' = requests \ {currentFloor}

Spec == Init /\ [][Next]_<<currentFloor, direction, requests>>

====
