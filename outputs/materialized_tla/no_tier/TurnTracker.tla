---- MODULE TurnTracker ----
EXTENDS Integers
CONSTANT MaxMoves
VARIABLES turn, moves

Init == turn = "X" /\ moves = 0

MoveX == turn = "X" /\ moves < MaxMoves
         /\ turn' = "O" /\ moves' = moves + 1

MoveO == turn = "O" /\ moves < MaxMoves
         /\ turn' = "X" /\ moves' = moves + 1

Next == MoveX \/ MoveO \/ UNCHANGED <<turn, moves>>

Spec == Init /\ [][Next]_<<turn, moves>>

TypeOK == turn \in {"X", "O"} /\ moves \in 0..MaxMoves

MovesInBounds == moves <= MaxMoves
====
