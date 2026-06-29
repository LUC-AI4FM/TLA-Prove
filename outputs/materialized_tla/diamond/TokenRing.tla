---- MODULE TokenRing ----
EXTENDS Naturals, Sequences

CONSTANT N
VARIABLES token, state

TypeOK == 
    /\ N \in Nat
    /\ N > 0
    /\ token \in 1..N
    /\ state \in [1..N -> {"CS", "NS"}]

(* Initial state *)
Init == 
    /\ token = 1
    /\ state = [i \in 1..N |-> IF i = 1 THEN "CS" ELSE "NS"]

(* Next-state relation *)
Next == 
    \E i \in 1..N :
        /\ token' = IF i = N THEN 1 ELSE i + 1
        /\ state' = [state EXCEPT ![i] = "CS", ![token'] = "NS"]

Spec == 
    /\ Init
    /\ [][Next]_<<token, state>>

====
