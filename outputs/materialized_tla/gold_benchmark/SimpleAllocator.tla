---- MODULE SimpleAllocator ----
EXTENDS Integers, FiniteSets

CONSTANT N
ASSUME N \in 1..5

Pages == 1..N
Clients == 1..N

VARIABLES free, allocated

TypeOK ==
    /\ free \subseteq Pages
    /\ allocated \in [Clients -> SUBSET Pages]

Init ==
    /\ free = Pages
    /\ allocated = [c \in Clients |-> {}]

Allocate(c) ==
    /\ c \in Clients
    /\ free # {}
    /\ \E p \in free :
        /\ free' = free \ {p}
        /\ allocated' = [allocated EXCEPT ![c] = @ \cup {p}]

Release(c) ==
    /\ c \in Clients
    /\ allocated[c] # {}
    /\ \E p \in allocated[c] :
        /\ allocated' = [allocated EXCEPT ![c] = @ \ {p}]
        /\ free' = free \cup {p}

Next == \E c \in Clients : Allocate(c) \/ Release(c)

SafeAllocation ==
    \A c1, c2 \in Clients :
        c1 # c2 => allocated[c1] \cap allocated[c2] = {}

vars == <<free, allocated>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK SafeAllocation
\* CONSTANT N = 3
