---- MODULE MultiProducerConsumer ----
EXTENDS Integers, Sequences

CONSTANTS N, B
VARIABLES buffer, producers


(* Define the type invariant *)
TypeOK == 
  /\ buffer \in Seq(1..100) \* Items are integers between 1 and 100
  /\ Len(buffer) <= B
  /\ producers \in [1..N -> {"idle", "producing"}]

(* Initial state: buffer is empty, all producers are idle *)
Init == 
  /\ buffer = <<>>
  /\ producers = [i \in 1..N |-> "idle"]

(* Define the Next-state relation *)
Next == 
  \/ \E i \in 1..N:
       /\ producers[i] = "idle"
       /\ Len(buffer) < B
       /\ producers' = [producers EXCEPT ![i] = "producing"]
       /\ buffer' = Append(buffer, i)  \* Producer i adds its ID to the buffer
  \/ \E i \in 1..N:
       /\ producers[i] = "producing"
       /\ Len(buffer) > 0
       /\ buffer' = SubSeq(buffer, 2, Len(buffer))  \* Consumer removes the first item
       /\ producers' = [producers EXCEPT ![i] = "idle"]

Spec == Init /\ [][Next]_<<buffer, producers>>

====
