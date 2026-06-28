---- MODULE DiningPhilosophers ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES forks, state

(* Type invariant *)
TypeOK == 
  /\ forks \in [1..N -> BOOLEAN]
  /\ state \in [1..N -> {"thinking", "hungry", "eating"}]

(* Helper functions *)
left(i) == IF i = 1 THEN N ELSE i - 1
right(i) == IF i = N THEN 1 ELSE i + 1

(* Philosopher i picks up forks if hungry and both forks are free *)
CanEat(i) == state[i] = "hungry" /\ forks[i] = FALSE /\ forks[right(i)] = FALSE

(* Next action *)
Next == 
  \E i \in 1..N :
    \/ (* Philosopher i becomes hungry *)
       /\ state' = [state EXCEPT ![i] = "hungry"]
       /\ forks' = forks
    \/ (* Philosopher i starts eating *)
       /\ CanEat(i)
       /\ state' = [state EXCEPT ![i] = "eating"]
       /\ forks' = [forks EXCEPT ![i] = TRUE, ![right(i)] = TRUE]
    \/ (* Philosopher i finishes eating *)
       /\ state[i] = "eating"
       /\ state' = [state EXCEPT ![i] = "thinking"]
       /\ forks' = [forks EXCEPT ![i] = FALSE, ![right(i)] = FALSE]

(* Initial condition *)
Init == 
  /\ forks = [i \in 1..N |-> FALSE]
  /\ state = [i \in 1..N |-> "thinking"]

Spec == Init /\ [][Next]_<<forks, state>>

====
