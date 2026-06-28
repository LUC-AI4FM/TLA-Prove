---- MODULE LamportsBakeryAlgorithm ----
EXTENDS Integers, Sequences, FiniteSets

Max(S) == CHOOSE x \in S : \A y \in S : x >= y

CONSTANTS N, Procs

VARIABLES num, flag

vars == <<num, flag>>

Init == /\ num = [i \in Procs |-> 0]
        /\ flag = [i \in Procs |-> FALSE]

ChoosePhase(i) == /\ flag' = [flag EXCEPT ![i] = TRUE]
                 /\ UNCHANGED <<num, flag>>

AssignNum(i) == /\ num' = [num EXCEPT ![i] = 1 + Max(num)]
               /\ flag' = [flag EXCEPT ![i] = FALSE]
               /\ UNCHANGED <<num, flag>>

Enter(i) == /\ ChoosePhase(i)
           /\ AssignNum(i)

Exit(i) == /\ flag' = [flag EXCEPT ![i] = FALSE]
          /\ UNCHANGED <<num, flag>>

Next == \E i \in Procs : Enter(i) \/ Exit(i)

Spec == Init /\ [][Next]_vars

TypeOK == /\ num \in [Procs -> Nat]
          /\ flag \in [Procs -> BOOLEAN]

IInv == /\ \A i, j \in Procs : i /= j => (flag[i] /\ flag[j] => (num[i] < num[j] \/ (num[i] = num[j] /\ i < j)))
Inv == /\ \A i, j \in Procs : i /= j => (flag[i] /\ flag[j] => (num[i] < num[j] \/ (num[i] = num[j] /\ i < j)))

====
