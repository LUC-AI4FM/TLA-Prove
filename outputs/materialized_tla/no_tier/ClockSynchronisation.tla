---- MODULE ClockSynchronisation ----
EXTENDS Naturals, Sequences, TLC, Integers

VARIABLES clocks, drift

CONSTANTS N, epsilon

TypeOK == 
  /\ clocks \in Seq(N)
  /\ drift \in Seq(N)

Init == 
  /\ clocks \in Seq(N)
  /\ drift \in Seq(N)
  /\ \A i \in 1..N : clocks[i] \in 0..1000
  /\ \A i \in 1..N : drift[i] \in -5..5

Sync == 
  /\ \A i \in 1..N : clocks[i] \in 0..1000
  /\ \A i \in 1..N : drift[i] \in -5..5

Next == 
  /\ clocks' \in Seq(N)
  /\ drift' \in Seq(N)
  /\ \A i \in 1..N : clocks'[i] \in 0..1000
  /\ \A i \in 1..N : drift'[i] \in -5..5
  /\ clocks' = clocks
  /\ drift' = drift
  /\ Sync
  /\ UNCHANGED <<clocks, drift>>

Spec == Init /\ [][Next]_<<clocks, drift>>

====
