---- MODULE BakeryAlgorithm ----
EXTENDS Integers, FiniteSets

CONSTANT N
ASSUME N \in 1..5

VARIABLES num, flag, pc

Procs == 1..N

TypeOK ==
    /\ num \in [Procs -> 0..20]
    /\ flag \in [Procs -> BOOLEAN]
    /\ pc \in [Procs -> {"idle", "doorway", "waiting", "critical"}]

Init ==
    /\ num = [p \in Procs |-> 0]
    /\ flag = [p \in Procs |-> FALSE]
    /\ pc = [p \in Procs |-> "idle"]

Max(S) == IF S = {} THEN 0
          ELSE CHOOSE x \in S : \A y \in S : x >= y

Doorway(p) ==
    /\ pc[p] = "idle"
    /\ Max({num[q] : q \in Procs}) < 18
    /\ flag' = [flag EXCEPT ![p] = TRUE]
    /\ num' = [num EXCEPT ![p] = Max({num[q] : q \in Procs}) + 1]
    /\ pc' = [pc EXCEPT ![p] = "doorway"]

FinishDoorway(p) ==
    /\ pc[p] = "doorway"
    /\ flag' = [flag EXCEPT ![p] = FALSE]
    /\ pc' = [pc EXCEPT ![p] = "waiting"]
    /\ UNCHANGED num

EnterCS(p) ==
    /\ pc[p] = "waiting"
    /\ \A q \in Procs \ {p} :
        /\ ~flag[q]
        /\ num[q] = 0 \/ num[p] < num[q] \/ (num[p] = num[q] /\ p < q)
    /\ pc' = [pc EXCEPT ![p] = "critical"]
    /\ UNCHANGED <<num, flag>>

ExitCS(p) ==
    /\ pc[p] = "critical"
    /\ num' = [num EXCEPT ![p] = 0]
    /\ pc' = [pc EXCEPT ![p] = "idle"]
    /\ UNCHANGED flag

Next == \E p \in Procs :
    Doorway(p) \/ FinishDoorway(p) \/ EnterCS(p) \/ ExitCS(p)

MutualExclusion ==
    \A p, q \in Procs :
        (p # q) => ~(pc[p] = "critical" /\ pc[q] = "critical")

vars == <<num, flag, pc>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK MutualExclusion
\* CONSTANT N = 2
