---- MODULE Dekker ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES turn, wants

Init == /\ turn \in {0,1}
        /\ wants \in SUBSET {0,1}
        /\ turn \in {0,1}
        /\ wants \subseteq {0,1}

Next == \/ /\ turn' = 1 - turn
          /\ wants' = {0,1}
        \/ /\ turn' = turn
          /\ wants' = {0,1} \ {turn}
          /\ turn \in {0,1}
          /\ wants \subseteq {0,1}

Spec == Init /\ [][Next]_<<turn, wants>>

TypeOK == /\ turn \in {0,1}
          /\ wants \subseteq {0,1}

====
