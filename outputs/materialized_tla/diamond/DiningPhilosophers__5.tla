---- MODULE DiningPhilosophers ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES forks, states

(* Constants *)
N == 5

(* Helper functions *)
LEFT(i) == IF i = 1 THEN N ELSE i - 1
RIGHT(i) == IF i = N THEN 1 ELSE i + 1

(* State predicates *)
ForkFree(i) == forks[i] = 0
ForkHeld(i, p) == forks[i] = p

PhilosopherState(i) == states[i]

Thinking(i) == states[i] = "thinking"
Hungry(i) == states[i] = "hungry"
Eating(i) == states[i] = "eating"

(* Initial state *)
Init == /\ forks = [i \in 1..N |-> 0]
        /\ states = [i \in 1..N |-> "thinking"]

(* Next-state relation *)
Next == 
  \/ \E i \in 1..N : 
       /\ states[i] = "thinking"
       /\ ForkFree(LEFT(i))
       /\ ForkFree(RIGHT(i))
       /\ states' = [states EXCEPT ![i] = "hungry"]
       /\ forks' = [forks EXCEPT ![LEFT(i)] = i, ![RIGHT(i)] = i]
  \/ \E i \in 1..N : 
       /\ states[i] = "hungry"
       /\ ForkHeld(LEFT(i), i)
       /\ ForkHeld(RIGHT(i), i)
       /\ states' = [states EXCEPT ![i] = "eating"]
       /\ forks' = forks
  \/ \E i \in 1..N : 
       /\ states[i] = "eating"
       /\ ForkHeld(LEFT(i), i)
       /\ ForkHeld(RIGHT(i), i)
       /\ states' = [states EXCEPT ![i] = "thinking"]
       /\ forks' = [forks EXCEPT ![LEFT(i)] = 0, ![RIGHT(i)] = 0]
  \/ \E i \in 1..N : 
       /\ states[i] = "hungry"
       /\ ForkFree(LEFT(i))
       /\ ForkFree(RIGHT(i))
       /\ states' = [states EXCEPT ![i] = "thinking"]
       /\ forks' = forks

(* Invariant: No fork is held by more than one philosopher *)
TypeOK == \A i \in 1..N : forks[i] \in 0..N

(* Specification *)
Spec == Init /\ [][Next]_<<forks, states>>

====
