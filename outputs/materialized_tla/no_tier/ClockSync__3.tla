---- MODULE ClockSync ----
EXTENDS Integers

CONSTANT N
ASSUME N \in 1..5

VARIABLES clock, synced

Nodes == 1..N

TypeOK ==
    /\ clock \in [Nodes -> 0..10]
    /\ synced \in [Nodes -> BOOLEAN]

Init ==
    /\ clock \in [Nodes -> 0..3]
    /\ synced = [n \in Nodes |-> FALSE]

Sync(i) ==
    /\ i \in Nodes
    /\ ~synced[i]
    /\ \E j \in Nodes :
        /\ j # i
        /\ LET avg == (clock[i] + clock[j]) \div 2
           IN clock' = [clock EXCEPT ![i] = avg]
    /\ synced' = [synced EXCEPT ![i] = TRUE]

Done ==
    /\ \A n \in Nodes : synced[n]
    /\ UNCHANGED <<clock, synced>>

Next == (\E i \in Nodes : Sync(i)) \/ Done

ClockBound ==
    (\A n \in Nodes : synced[n])
        => \A i, j \in Nodes : clock[i] - clock[j] \in -5..5

vars == <<clock, synced>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK ClockBound
\* CONSTANT N = 3
