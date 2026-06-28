---- MODULE ReadWriteLock ----
EXTENDS Integers, Sequences, FiniteSets
CONSTANTS Actors

VARIABLES readers, writer_active

Init == 
  /\ readers = {}
  /\ writer_active = FALSE

TryRead(actor) == 
  /\ actor \notin readers
  /\ writer_active = FALSE
  /\ readers' = readers \cup {actor}
  /\ writer_active' = writer_active

TryWrite(actor) == 
  /\ actor \notin readers
  /\ writer_active = FALSE
  /\ writer_active' = TRUE
  /\ readers' = readers

StopRead(actor) == 
  /\ actor \in readers
  /\ readers' = readers \ {actor}
  /\ writer_active' = writer_active

StopWrite(actor) == 
  /\ writer_active = TRUE
  /\ writer_active' = FALSE
  /\ readers' = readers

Stop(actor) == 
  \/ StopRead(actor)
  \/ StopWrite(actor)

Next == 
  \/ \E actor \in Actors : TryRead(actor)
  \/ \E actor \in Actors : TryWrite(actor)
  \/ \E actor \in Actors : Stop(actor)

Spec == Init /\ [][Next]_<<readers, writer_active>>

TypeOK == 
  /\ readers \subseteq Actors
  /\ writer_active \in BOOLEAN

Safety == 
  \A actor \in Actors : (actor \in readers) => (writer_active = FALSE)

Fairness == 
  WF_ <<readers, writer_active>> (Next)

Liveness == 
  \A actor \in Actors : (actor \in Actors) => (<> (actor \in readers \/ writer_active))

====
