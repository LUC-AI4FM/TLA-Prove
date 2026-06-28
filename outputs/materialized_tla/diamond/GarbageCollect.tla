---- MODULE GarbageCollect ----
EXTENDS Integers

CONSTANT Max

VARIABLES alloc, marked, phase

vars == <<alloc, marked, phase>>

Init == alloc = 0 /\ marked = 0 /\ phase = 0

AllocObj == phase = 0 /\ alloc < Max /\ alloc' = alloc + 1 /\ UNCHANGED <<marked, phase>>

StartMark == phase = 0 /\ alloc > 0 /\ phase' = 1 /\ UNCHANGED <<alloc, marked>>

MarkObj == phase = 1 /\ marked < alloc /\ marked' = marked + 1 /\ UNCHANGED <<alloc, phase>>

StartSweep == phase = 1 /\ phase' = 2 /\ UNCHANGED <<alloc, marked>>

Sweep == phase = 2 /\ alloc' = marked /\ marked' = 0 /\ phase' = 0

Next == AllocObj \/ StartMark \/ MarkObj \/ StartSweep \/ Sweep \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == alloc \in 0..Max /\ marked \in 0..Max /\ phase \in {0, 1, 2}

SafetyBounded == marked <= alloc /\ alloc <= Max
====
