---- MODULE SimpleAllocator ----
EXTENDS Integers, FiniteSets

CONSTANTS N, Clients

Pages == 1..N

VARIABLES free, allocated

Init == 
    /\ free = Pages
    /\ allocated = [c \in Clients |-> {}]

Request(c, P) == 
    /\ P \subseteq free
    /\ free' = free \ P
    /\ allocated' = [allocated EXCEPT ![c] = @ \cup P]

Release(c, P) ==
    /\ P \subseteq allocated[c]
    /\ free' = free \cup P
    /\ allocated' = [allocated EXCEPT ![c] = @ \ P]

Next == \E c \in Clients : 
            \E P \in SUBSET Pages : 
                Request(c, P) \/ Release(c, P)

Spec == Init /\ [][Next]_<<free, allocated>>

TypeInvariant == 
    /\ free \subseteq Pages
    /\ \A c \in Clients : allocated[c] \subseteq Pages
    /\ \A p \in Pages : (p \in free) <=> (\A c \in Clients : ~(p \in allocated[c]))

====
