---- MODULE GossipRumor ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N

VARIABLES known, rumor

(* 
   known[i] is the set of nodes that node i knows the rumor from.
   rumor is the set of nodes that have heard the rumor at all.
*)

Init == 
    /\ known = [i \in 1..N |-> {}]
    /\ rumor = {}

Next == 
    \E i \in 1..N:
        LET j == CHOOSE k \in 1..N : k # i IN
        /\ known' = [known EXCEPT ![i] = known[i] \cup {j}]
        /\ rumor' = rumor \cup {i, j}

Spec == Init /\ [][Next]_<<known, rumor>>

====
