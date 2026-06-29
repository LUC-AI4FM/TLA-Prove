---- MODULE MultiProducerConsumer ----
EXTENDS Integers, Sequences, FiniteSets

VARIABLES buffer, producers, consumer

Init ==
  /\ buffer = <<>>
  /\ producers = <<>>
  /\ consumer = 0

Next ==
  \/ /\ producers' = <<>>
     /\ consumer' = 0
     /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = Append(buffer, p)
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0
        /\ buffer' = <<>>
  \/ /\ \E p \in 1..Len(producers) :
        /\ producers' = <<>>
        /\ consumer' = 0

====
