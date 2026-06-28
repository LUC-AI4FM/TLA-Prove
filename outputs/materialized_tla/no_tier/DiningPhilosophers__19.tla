---- MODULE DiningPhilosophers ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES forks, state

(* State of each philosopher: 0=Thinking, 1=Hungry, 2=Eating *)
State == 0 .. 2

(* Initial state: all thinking, all forks free *)
Init == forks = [i \in 1..N |-> 0] /\ state = [i \in 1..N |-> 0]

(* Helper: left and right neighbor indices (circular) *)
Left(i) == IF i = 1 THEN N ELSE i - 1
Right(i) == IF i = N THEN 1 ELSE i + 1

(* Action: philosopher i starts eating if both forks are free *)
Take(i) == 
  /\ state[i] = 1
  /\ forks[i] = 0
  /\ forks[Right(i)] = 0
  /\ forks' = [forks EXCEPT ![i] = 1, ![Right(i)] = 1]
  /\ state' = [state EXCEPT ![i] = 2]

(* Action: philosopher i finishes eating and puts down forks *)
Put(i) == 
  /\ state[i] = 2
  /\ forks' = [forks EXCEPT ![i] = 0, ![Right(i)] = 0]
  /\ state' = [state EXCEPT ![i] = 0]

(* Action: philosopher i becomes hungry *)
Hungry(i) == 
  /\ state[i] = 0
  /\ state' = [state EXCEPT ![i] = 1]
  /\ UNCHANGED <<forks>>

Next == \E i \in 1..N: Take(i) \/ Put(i) \/ Hungry(i)

Spec == Init /\ [][Next]_<<forks, state>>

TypeOK == 
  /\ forks \in [1..N -> 0..2]
  /\ state \in [1..N -> State]
====
