---- MODULE Elevator ----
EXTENDS Integers, Sequences, FiniteSets
Min(S) == CHOOSE x \in S : \A y \in S : x =< y


CONSTANT N \* Number of floors, N >= 1

VARIABLES pos, dir, req

(*
  pos  : current floor (1..N)
  dir  : direction of movement, 1 for up, -1 for down, 0 for idle
  req  : set of floors with pending requests
*)

(* Helper to check if there are pending requests in a given direction *)
HasReqInDir(d) == 
  \E f \in req :
    IF d = 1 THEN f > pos ELSE f < pos

(* Helper to check if current floor has a request *)
AtRequest == pos \in req

Init == 
  /\ pos = 1
  /\ dir = 0
  /\ req = {}

(* Elevator movement logic *)
Move ==
  /\ dir /= 0
  /\ LET next == pos + dir IN
     /\ next >= 1
     /\ next <= N
     /\ pos' = next
  /\ dir' = dir
  /\ req' = req

(* Door operation: clear request at current floor *)
OpenDoor ==
  /\ AtRequest
  /\ pos' = pos
  /\ dir' = dir
  /\ req' = req \ {pos}

(* Idle behavior: stay in place *)
Idle ==
  /\ dir = 0
  /\ pos' = pos
  /\ req' = req

(* Request handling *)
Request(f) ==
  /\ f \in 1..N
  /\ req' = req \cup {f}
  /\ UNCHANGED <<pos, dir>>

(* Direction update when no more requests in current direction *)
UpdateDir ==
  /\ dir /= 0
  /\ ~HasReqInDir(dir)
  /\ dir' = IF dir = 1 THEN -1 ELSE 1
  /\ UNCHANGED <<pos, req>>

(* Idle direction update when no pending requests *)
UpdateIdle ==
  /\ dir = 0
  /\ req # {}
  /\ dir' = IF Min(req) < pos THEN -1 ELSE 1
  /\ UNCHANGED <<pos, req>>

(* Idle update when no requests *)
NoReq ==
  /\ dir = 0
  /\ req = {}
  /\ UNCHANGED <<pos, dir>>

Next ==
  \E f \in 1..N : Request(f) \/
  IF AtRequest THEN OpenDoor ELSE
    IF HasReqInDir(dir) THEN Move ELSE UpdateDir
  /\ IF req # {} THEN UpdateIdle ELSE NoReq

Spec == Init /\ [][Next]_<<pos, dir, req>>

(* Invariant: position always within bounds *)
TypeOK == 
  /\ pos \in 1..N
  /\ dir \in {-1, 0, 1}
  /\ req \subseteq 1..N
====
