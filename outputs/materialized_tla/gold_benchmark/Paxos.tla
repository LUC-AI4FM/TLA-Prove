---- MODULE Paxos ----
EXTENDS Integers, FiniteSets

CONSTANT N
ASSUME N \in 1..5

Acceptors == 1..N
Values == {1, 2}
Ballots == 0..4

VARIABLES maxBal, maxVBal, maxVal, chosen

TypeOK ==
    /\ maxBal \in [Acceptors -> -1..4]
    /\ maxVBal \in [Acceptors -> -1..4]
    /\ maxVal \in [Acceptors -> Values \cup {-1}]
    /\ chosen \in Values \cup {-1}

Init ==
    /\ maxBal = [a \in Acceptors |-> -1]
    /\ maxVBal = [a \in Acceptors |-> -1]
    /\ maxVal = [a \in Acceptors |-> -1]
    /\ chosen = -1

Quorum == {Q \in SUBSET Acceptors : Cardinality(Q) * 2 > N}

Prepare(b) ==
    /\ b \in Ballots
    /\ \E Q \in Quorum :
        /\ \A a \in Q : maxBal[a] < b
        /\ maxBal' = [a \in Acceptors |->
            IF a \in Q THEN b ELSE maxBal[a]]
    /\ UNCHANGED <<maxVBal, maxVal, chosen>>

Accept(b, v) ==
    /\ b \in Ballots
    /\ v \in Values
    /\ \E Q \in Quorum :
        /\ \A a \in Q : maxBal[a] = b
        /\ LET promisedVals == {maxVal[a] : a \in Q} \ {-1}
           IN \/ promisedVals = {}
              \/ v \in promisedVals
        /\ maxVBal' = [a \in Acceptors |->
            IF a \in Q THEN b ELSE maxVBal[a]]
        /\ maxVal' = [a \in Acceptors |->
            IF a \in Q THEN v ELSE maxVal[a]]
        /\ maxBal' = [a \in Acceptors |->
            IF a \in Q THEN b ELSE maxBal[a]]
    /\ UNCHANGED chosen

Choose ==
    /\ chosen = -1
    /\ \E v \in Values :
        /\ \E Q \in Quorum :
            \A a \in Q : maxVal[a] = v
        /\ chosen' = v
    /\ UNCHANGED <<maxBal, maxVBal, maxVal>>

Next ==
    \/ \E b \in Ballots : Prepare(b)
    \/ \E b \in Ballots : \E v \in Values : Accept(b, v)
    \/ Choose

Consistency == chosen # -1 => chosen \in Values

vars == <<maxBal, maxVBal, maxVal, chosen>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK Consistency
\* CONSTANT N = 3
