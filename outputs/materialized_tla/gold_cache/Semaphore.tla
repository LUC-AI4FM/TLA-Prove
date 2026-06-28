---- MODULE Semaphore ----
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANT N

VARIABLES count, proc

(* Types *)
TypeOK == 
    /\ count \in 0..N
    /\ proc \subseteq 1..N
    /\ count + Cardinality(proc) = N

(* Initial state: semaphore count is N, no process holds it *)
Init == 
    /\ count = N
    /\ proc = {}

(* Process actions *)
Acquire == 
    \E p \in 1..N :
        /\ ~(p \in proc)
        /\ count > 0
        /\ proc' = proc \cup {p}
        /\ count' = count - 1

Release == 
    \E p \in proc :
        /\ proc' = proc \ {p}
        /\ count' = count + 1

(* Next-state relation *)
Next == Acquire \/ Release

Spec == Init /\ [][Next]_<<count, proc>>

====
