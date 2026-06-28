---- MODULE RateLimiter ----
EXTENDS Integers
CONSTANT Max
VARIABLES tokens, requests

Init == tokens = Max /\ requests = 0

Consume == tokens > 0 /\ requests < Max * 2
           /\ tokens' = tokens - 1 /\ requests' = requests + 1

Refill == tokens < Max
          /\ tokens' = tokens + 1 /\ UNCHANGED requests

Next == Consume \/ Refill \/ UNCHANGED <<tokens, requests>>

Spec == Init /\ [][Next]_<<tokens, requests>>

TypeOK == tokens \in 0..Max /\ requests \in 0..(Max * 2)

TokensBounded == tokens >= 0 /\ tokens <= Max

SafetyInv == tokens >= 0
====
