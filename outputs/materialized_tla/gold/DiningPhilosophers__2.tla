---- MODULE DiningPhilosophers ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES forks, states

(* Forks: array of length N, each element is 0 (free) or philosopher index (1..N) holding it *)
(* States: array of length N, each element is "thinking", "hungry", or "eating" *)

(* Helper functions *)
Left(i) == IF i = 1 THEN N ELSE i - 1
Right(i) == IF i = N THEN 1 ELSE i + 1

(* Type invariant *)
TypeOK == 
    /\ forks \in [1..N -> 0..N]
    /\ states \in [1..N -> {"thinking", "hungry", "eating"}]

(* Initial state: all forks free, all philosophers thinking *)
Init == 
    /\ forks = [i \in 1..N |-> 0]
    /\ states = [i \in 1..N |-> "thinking"]

(* Action: philosopher i becomes hungry *)
Hungry(i) == 
    /\ states[i] = "thinking"
    /\ states' = [states EXCEPT ![i] = "hungry"]
    /\ forks' = forks

(* Action: philosopher i picks up forks if both are free *)
PickUp(i) == 
    /\ states[i] = "hungry"
    /\ forks[Left(i)] = 0
    /\ forks[Right(i)] = 0
    /\ forks' = [forks EXCEPT ![Left(i)] = i, ![Right(i)] = i]
    /\ states' = [states EXCEPT ![i] = "eating"]

(* Action: philosopher i puts down forks *)
PutDown(i) == 
    /\ states[i] = "eating"
    /\ forks' = [forks EXCEPT ![Left(i)] = 0, ![Right(i)] = 0]
    /\ states' = [states EXCEPT ![i] = "thinking"]

(* Next-state relation: any philosopher can become hungry, pick up forks, or put down forks *)
Next == 
    \E i \in 1..N :
        (Hungry(i) \/ PickUp(i) \/ PutDown(i))

Spec == Init /\ [][Next]_<<forks, states>>

====
