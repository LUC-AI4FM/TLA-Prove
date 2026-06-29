---- MODULE GossipProtocol ----
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS N, Node, InfectedMessageType, InfectionMessageType

VARIABLES known, infected

Init == /\ known = [n \in Node |-> {n}]
        /\ infected = [n \in Node |-> FALSE]

Next == \E n \in Node :
          /\ known' = [known EXCEPT ![n] = known[n] \cup {m \in Node : m \in known[n] /\ infected[m]}]
          /\ infected' = [infected EXCEPT ![n] = infected[n] \/ (\E m \in Node : m \in known[n] /\ infected[m])]

Spec == Init /\ [][Next]_<<known, infected>>

TypeInvariant == /\ known \in [Node -> SUBSET Node]
                 /\ infected \in [Node -> BOOLEAN]

====
