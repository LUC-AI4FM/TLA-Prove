---- MODULE MultiProducerConsumer ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES buffer, count

Init == /\ buffer = <<>>
        /\ count = 0

Next == \/ /\ count < 10
           /\ buffer' = Append(buffer, 1)
           /\ count' = count + 1
       \/ /\ count > 0
           /\ buffer' = Tail(buffer)
           /\ count' = count - 1

Spec == Init /\ [][Next]_<<buffer, count>>

====
