---- MODULE DekkersAlgorithm ----
EXTENDS Integers

VARIABLES wants, turn, pc

Procs == {0, 1}

Other(p) == 1 - p

TypeOK ==
    /\ wants \in [Procs -> BOOLEAN]
    /\ turn \in Procs
    /\ pc \in [Procs -> {"idle", "set_flag", "check", "wait", "critical", "exit"}]

Init ==
    /\ wants = [p \in Procs |-> FALSE]
    /\ turn = 0
    /\ pc = [p \in Procs |-> "idle"]

SetFlag(p) ==
    /\ pc[p] = "idle"
    /\ wants' = [wants EXCEPT ![p] = TRUE]
    /\ pc' = [pc EXCEPT ![p] = "set_flag"]
    /\ UNCHANGED turn

Check(p) ==
    /\ pc[p] = "set_flag"
    /\ IF ~wants[Other(p)]
       THEN pc' = [pc EXCEPT ![p] = "critical"]
       ELSE pc' = [pc EXCEPT ![p] = "check"]
    /\ UNCHANGED <<wants, turn>>

Wait(p) ==
    /\ pc[p] = "check"
    /\ wants[Other(p)]
    /\ IF turn # p
       THEN /\ wants' = [wants EXCEPT ![p] = FALSE]
            /\ pc' = [pc EXCEPT ![p] = "wait"]
       ELSE /\ pc' = [pc EXCEPT ![p] = "set_flag"]
            /\ UNCHANGED wants
    /\ UNCHANGED turn

WaitForTurn(p) ==
    /\ pc[p] = "wait"
    /\ turn = p
    /\ wants' = [wants EXCEPT ![p] = TRUE]
    /\ pc' = [pc EXCEPT ![p] = "set_flag"]
    /\ UNCHANGED turn

EnterFromCheck(p) ==
    /\ pc[p] = "check"
    /\ ~wants[Other(p)]
    /\ pc' = [pc EXCEPT ![p] = "critical"]
    /\ UNCHANGED <<wants, turn>>

ExitCS(p) ==
    /\ pc[p] = "critical"
    /\ turn' = Other(p)
    /\ wants' = [wants EXCEPT ![p] = FALSE]
    /\ pc' = [pc EXCEPT ![p] = "idle"]

Next == \E p \in Procs :
    SetFlag(p) \/ Check(p) \/ Wait(p) \/ WaitForTurn(p)
    \/ EnterFromCheck(p) \/ ExitCS(p)

MutualExclusion ==
    ~(pc[0] = "critical" /\ pc[1] = "critical")

Deadlock_Freedom ==
    (wants[0] \/ wants[1]) =>
        (pc[0] \in {"critical", "set_flag", "check", "wait"}
         \/ pc[1] \in {"critical", "set_flag", "check", "wait"})

vars == <<wants, turn, pc>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK MutualExclusion
