---- MODULE ResourceAlloc ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES owner, requests, releases

Init == /\ owner = 0
        /\ requests = {}
        /\ releases = {}

Acquire == /\ owner # 0
          /\ owner' = owner
          /\ requests' = requests
          /\ releases' = releases

Request == /\ owner = 0
          /\ owner' = 1
          /\ requests' = requests
          /\ releases' = releases

Release == /\ owner = 1
          /\ owner' = 0
          /\ requests' = requests
          /\ releases' = releases

Next == \/ Acquire
        \/ Request
        \/ Release

Spec == Init /\ [][Next]_<<owner, requests, releases>>

====
