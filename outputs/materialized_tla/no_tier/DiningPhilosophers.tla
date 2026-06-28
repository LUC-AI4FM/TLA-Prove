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

(* Initial state *)
Init == /\ forks = [i \in 1..N |-> "free"]
        /\ states = [i \in 1..N |-> "thinking"]

(* Next-state relation *)
Next == \/ \E i \in 1..N :
          /\ IsThinking(i)
          /\ forks[LEFT(i)] = "free"
          /\ forks[RIGHT(i)] = "free"
          /\ states' = [states EXCEPT ![i] = "hungry"]
          /\ forks' = forks
        \/ \E i \in 1..N :
          /\ IsHungry(i)
          /\ forks[LEFT(i)] = "free"
          /\ forks[RIGHT(i)] = "free"
          /\ states' = [states EXCEPT ![i] = "eating"]
          /\ forks' = [forks EXCEPT ![LEFT(i)] = "occupied", ![RIGHT(i)] = "occupied"]
        \/ \E i \in 1..N :
          /\ IsEating(i)
          /\ forks[LEFT(i)] = "occupied"
          /\ forks[RIGHT(i)] = "occupied"
          /\ states' = [states EXCEPT ![i] = "thinking"]
          /\ forks' = [forks EXCEPT ![LEFT(i)] = "free", ![RIGHT(i)] = "free"]

(* Invariant: No two adjacent philosophers are eating simultaneously *)
NoAdjacentEating == \A i \in 1..N :
                     /\ IsEating(i)
                     => forks[LEFT(i)] = "free" /\ forks[RIGHT(i)] = "free"

(* Type invariant *)
TypeOK == /\ forks \in [1..N -> {"free", "occupied"}]
          /\ states \in [1..N -> {"thinking", "hungry", "eating"}]

Spec == Init /\ [][Next]_<<forks, states>>

====
