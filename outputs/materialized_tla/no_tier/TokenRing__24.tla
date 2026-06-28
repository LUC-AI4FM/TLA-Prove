---- MODULE TokenRing ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS N, M, Node

VARIABLE c

Init == /\ c \in [Node -> 0 .. M - 1]

CreateToken == /\ c[0] = c[N - 1]
              /\ c' = [c EXCEPT ![0] = (c[N - 1] + 1) % M]

PassToken(i) == /\ i /= 0
               /\ c[i] /= c[i - 1]
               /\ c' = [c EXCEPT ![i] = c[i - 1]]

Next == CreateToken \/ \E i \in Node : PassToken(i)

Spec == Init /\ [][Next]_<<c>> /\ WF_<<c>>(Next)

TypeOK == /\ c \in [Node -> 0 .. M - 1]
          /\ N \in Nat
          /\ M \in Nat
          /\ M > 0
          /\ N > 0

====
