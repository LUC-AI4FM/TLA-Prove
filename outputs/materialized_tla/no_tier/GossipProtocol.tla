---- MODULE GossipProtocol ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N, known

VARIABLES infected

Init == /\ infected = <<>> 
        /\ Len(infected) = N
        /\ \A i \in 1..N : infected[i] = FALSE

Next == /\ \E i \in 1..N :
          /\ infected' = [j \in 1..N |-> IF j = i THEN TRUE ELSE infected[j]]
          /\ \E j \in 1..N :
                /\ j # i
                /\ infected[j] = FALSE
                /\ infected' = [k \in 1..N |-> IF k = j THEN TRUE ELSE infected'[k]]

Spec == Init /\ [][Next]_<<infected>>

====
