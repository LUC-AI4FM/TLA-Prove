---- MODULE LeaseProtocol ----
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS N, T  \* Number of nodes and lease duration

VARIABLES owner, lease, time

(* owner: node that holds the lease or 0 if none
   lease: remaining lease time (0 if no lease)
   time: global time counter (for simulation) *)

(* Helper to get the set of nodes *)
Nodes == 1..N

(* Initial state: no owner, no lease, time 0 *)
Init == /\ owner = 0
        /\ lease = 0
        /\ time = 0

(* Action: a node requests the lease *)
Request(i) ==
  /\ i \in Nodes
  /\ owner = 0
  /\ lease = 0
  /\ owner' = i
  /\ lease' = T
  /\ time' = time

(* Action: the lease expires *)
Expire ==
  /\ lease > 0
  /\ lease' = lease - 1
  /\ owner' = IF lease' = 0 THEN 0 ELSE owner
  /\ time' = time

(* Action: a node releases the lease early *)
Release(i) ==
  /\ i = owner
  /\ lease = 0
  /\ owner' = 0
  /\ time' = time

(* Next-state relation *)
Next == \/ \E i \in Nodes : Request(i)
        \/ Expire
        \/ \E i \in Nodes : Release(i)

(* Invariant: owner is either 0 or a valid node *)
TypeOK == owner \in 0..N /\ lease \in 0..T /\ time \in Nat

Spec == Init /\ [][Next]_<<owner, lease, time>>

====
