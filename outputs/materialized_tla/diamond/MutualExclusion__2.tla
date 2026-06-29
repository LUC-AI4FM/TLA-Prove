---- MODULE MutualExclusion ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS Idle, Trying, Critical, N

VARIABLES state, turn

(* Type invariant *)
TypeOK == 
  /\ state \in [1..N -> {Idle, Trying, Critical}]
  /\ turn \in 1..N

(* Initial state *)
Init == 
  /\ turn = 1
  /\ state = [p \in 1..N |-> Idle]

(* Next-state relation *)
Next == 
  \/ \E p \in 1..N :
       /\ state[p] = Idle
       /\ state' = [state EXCEPT ![p] = Trying]
       /\ turn' = turn
  \/ \E p \in 1..N :
       /\ state[p] = Trying
       /\ turn = p
       /\ state' = [state EXCEPT ![p] = Critical]
       /\ turn' = turn
  \/ \E p \in 1..N :
       /\ state[p] = Critical
       /\ state' = [state EXCEPT ![p] = Idle]
       /\ turn' = (turn % N) + 1

(* Specification *)
Spec == Init /\ [][Next]_<<state, turn>>

====
