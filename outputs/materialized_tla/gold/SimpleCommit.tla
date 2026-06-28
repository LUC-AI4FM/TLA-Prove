---- MODULE SimpleCommit ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N, Participants
VARIABLES coordinator, participants


vars == << coordinator, participants >>

Init == /\ coordinator = 0
      /\ participants = [p \in Participants |-> 0]

Next == /\ coordinator' = 1
      /\ participants' = [p \in Participants |-> IF p \in {1, 2, 3} THEN 1 ELSE 0]

Spec == Init /\ [][Next]_vars

====
