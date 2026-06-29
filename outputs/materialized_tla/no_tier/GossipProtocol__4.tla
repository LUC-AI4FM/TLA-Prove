---- MODULE GossipProtocol ----
EXTENDS Integers, FiniteSets

CONSTANTS N

VARIABLES known, infected

Init == /\ known = [i \in 1..N |-> {}]
        /\ infected = [i \in 1..N |-> FALSE]

Next == \E i \in 1..N :
          /\ known' = [known EXCEPT ![i] = known[i] \cup {j \in 1..N : infected[j]}]
          /\ infected' = [infected EXCEPT ![i] = TRUE]

Spec == Init /\ [][Next]_<<known, infected>>

====
