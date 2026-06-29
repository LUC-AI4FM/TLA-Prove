---- MODULE DiningPhilosophers ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES forks, states

(* Constants *)
N == 5

(* Helper functions *)
LEFT(i) == IF i = 1 THEN N ELSE i - 1
RIGHT(i) == IF i = N THEN 1 ELSE i + 1

(* State definitions *)
THINKING == 0
HUNGRY == 1
EATING == 2

(* Type invariant *)
TypeOK == 
  /\ forks \in [1..N -> 0..N]
  /\ states \in [1..N -> {THINKING, HUNGRY, EATING}]

(* Initial state *)
Init == 
  /\ forks = [i \in 1..N |-> 0]
  /\ states = [i \in 1..N |-> THINKING]

(* Next-state relation *)
Next == 
  \E i \in 1..N :
    \/ (* Philosopher i becomes hungry *)
       /\ states[i] = THINKING
       /\ states' = [states EXCEPT ![i] = HUNGRY]
       /\ forks' = forks
    \/ (* Philosopher i starts eating if both forks are free *)
       /\ states[i] = HUNGRY
       /\ forks[i] = 0
       /\ forks[LEFT(i)] = 0
       /\ forks' = [forks EXCEPT ![i] = i, ![LEFT(i)] = i]
       /\ states' = [states EXCEPT ![i] = EATING]
    \/ (* Philosopher i puts down forks after eating *)
       /\ states[i] = EATING
       /\ forks' = [forks EXCEPT ![i] = 0, ![LEFT(i)] = 0]
       /\ states' = [states EXCEPT ![i] = THINKING]

(* Temporal specification *)
Spec == Init /\ [][Next]_<<forks, states>>

====
