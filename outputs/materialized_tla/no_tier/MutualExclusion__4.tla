---- MODULE MutualExclusion ----
EXTENDS Integers

CONSTANT N
ASSUME N \in 1..10

VARIABLE pc

Procs == 1..N

TypeOK == pc \in [Procs -> {"idle", "trying", "critical"}]

Init == pc = [p \in Procs |-> "idle"]

TryEnter(p) ==
    /\ pc[p] = "idle"
    /\ pc' = [pc EXCEPT ![p] = "trying"]

Enter(p) ==
    /\ pc[p] = "trying"
    /\ \A q \in Procs : q # p => pc[q] # "critical"
    /\ pc' = [pc EXCEPT ![p] = "critical"]

Exit(p) ==
    /\ pc[p] = "critical"
    /\ pc' = [pc EXCEPT ![p] = "idle"]

Next == \E p \in Procs : TryEnter(p) \/ Enter(p) \/ Exit(p)

MutualExclusion == \A p, q \in Procs :
    (p # q) => ~(pc[p] = "critical" /\ pc[q] = "critical")

vars == <<pc>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK MutualExclusion
\* CONSTANT N = 3
