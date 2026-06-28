---- MODULE DiningPhilosophers ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES forks, states

(* Constants *)
N == 5

(* Helper functions *)
LEFT(i) == IF i = 1 THEN N ELSE i - 1
RIGHT(i) == IF i = N THEN 1 ELSE i + 1

(* State predicates *)
IsThinking(i) == states[i] = "thinking"
IsHungry(i) == states[i] = "hungry"
IsEating(i) == states[i] = "eating"

(* Type invariants *)
TypeOK == 
  /\ forks \in [1..N -> {"free", "held"}]
  /\ states \in [1..N -> {"thinking", "hungry", "eating"}]

(* Initial state *)
Init == 
  /\ forks = [i \in 1..N |-> "free"]
  /\ states = [i \in 1..N |-> "thinking"]

(* Next-state relation *)
Next == 
  \E i \in 1..N :
    \/ (IsHungry(i) /\ forks[LEFT(i)] = "free" /\ forks[RIGHT(i)] = "free" /\ 
        states' = [states EXCEPT ![i] = "eating"] /\ 
        forks' = [forks EXCEPT ![LEFT(i)] = "held", ![RIGHT(i)] = "held"])
    \/ (IsEating(i) /\ forks[LEFT(i)] = "held" /\ forks[RIGHT(i)] = "held" /\ 
        states' = [states EXCEPT ![i] = "thinking"] /\ 
        forks' = [forks EXCEPT ![LEFT(i)] = "free", ![RIGHT(i)] = "free"])
    \/ (IsThinking(i) /\ forks[i] = "free" /\ 
        states' = [states EXCEPT ![i] = "hungry"] /\ forks' = forks)

Spec == Init /\ [][Next]_<<forks, states>>

====
