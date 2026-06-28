---- MODULE TwoPhaseCommit ----
EXTENDS Integers
VARIABLES coordState, p1Vote, p2Vote
vars == <<coordState, p1Vote, p2Vote>>

Init == coordState = "init" /\ p1Vote = "none" /\ p2Vote = "none"

Prepare == /\ coordState = "init"
           /\ coordState' = "waiting"
           /\ p1Vote' = p1Vote
           /\ p2Vote' = p2Vote

P1VoteYes == /\ coordState = "waiting" /\ p1Vote = "none"
             /\ p1Vote' = "yes"
             /\ coordState' = coordState
             /\ p2Vote' = p2Vote

P1VoteNo == /\ coordState = "waiting" /\ p1Vote = "none"
            /\ p1Vote' = "no"
            /\ coordState' = coordState
            /\ p2Vote' = p2Vote

P2VoteYes == /\ coordState = "waiting" /\ p2Vote = "none"
             /\ p2Vote' = "yes"
             /\ coordState' = coordState
             /\ p1Vote' = p1Vote

P2VoteNo == /\ coordState = "waiting" /\ p2Vote = "none"
            /\ p2Vote' = "no"
            /\ coordState' = coordState
            /\ p1Vote' = p1Vote

DecideCommit == /\ coordState = "waiting"
                /\ p1Vote = "yes" /\ p2Vote = "yes"
                /\ coordState' = "committed"
                /\ p1Vote' = p1Vote
                /\ p2Vote' = p2Vote

DecideAbort == /\ coordState = "waiting"
               /\ p1Vote /= "none" /\ p2Vote /= "none"
               /\ ~(p1Vote = "yes" /\ p2Vote = "yes")
               /\ coordState' = "aborted"
               /\ p1Vote' = p1Vote
               /\ p2Vote' = p2Vote

Next == Prepare \/ P1VoteYes \/ P1VoteNo \/ P2VoteYes \/ P2VoteNo
        \/ DecideCommit \/ DecideAbort
        \/ UNCHANGED vars

Spec == Init /\ [][Next]_vars

TypeOK == coordState \in {"init", "waiting", "committed", "aborted"}
          /\ p1Vote \in {"none", "yes", "no"}
          /\ p2Vote \in {"none", "yes", "no"}

SafetyInv == coordState = "committed" => (p1Vote = "yes" /\ p2Vote = "yes")
====
