---- MODULE BoundedRetransmission ----
EXTENDS Integers

CONSTANTS N, MAX

ASSUME N \in 1..10
ASSUME MAX \in 1..10

VARIABLES sChunk, rChunk, retry, sDone, rDone, channel

TypeOK ==
    /\ sChunk \in 1..(N + 1)
    /\ rChunk \in 0..N
    /\ retry \in 0..MAX
    /\ sDone \in {"sending", "ok", "nok"}
    /\ rDone \in {"receiving", "ok", "nok"}
    /\ channel \in {"empty", "data", "lost", "ack", "ack_lost"}

Init ==
    /\ sChunk = 1
    /\ rChunk = 0
    /\ retry = 0
    /\ sDone = "sending"
    /\ rDone = "receiving"
    /\ channel = "empty"

Send ==
    /\ sDone = "sending"
    /\ sChunk <= N
    /\ channel = "empty"
    /\ channel' = "data"
    /\ UNCHANGED <<sChunk, rChunk, retry, sDone, rDone>>

Lose ==
    /\ channel = "data"
    /\ channel' = "lost"
    /\ UNCHANGED <<sChunk, rChunk, retry, sDone, rDone>>

Deliver ==
    /\ channel = "data"
    /\ rChunk' = sChunk
    /\ channel' = "ack"
    /\ UNCHANGED <<sChunk, retry, sDone, rDone>>

LoseAck ==
    /\ channel = "ack"
    /\ channel' = "ack_lost"
    /\ UNCHANGED <<sChunk, rChunk, retry, sDone, rDone>>

RecvAck ==
    /\ channel = "ack"
    /\ retry' = 0
    /\ IF sChunk = N
       THEN /\ sDone' = "ok"
            /\ rDone' = "ok"
            /\ sChunk' = N + 1
       ELSE /\ sChunk' = sChunk + 1
            /\ UNCHANGED <<sDone, rDone>>
    /\ channel' = "empty"
    /\ UNCHANGED rChunk

Timeout ==
    /\ channel \in {"lost", "ack_lost"}
    /\ sDone = "sending"
    /\ IF retry < MAX
       THEN /\ retry' = retry + 1
            /\ channel' = "empty"
            /\ UNCHANGED <<sChunk, rChunk, sDone, rDone>>
       ELSE /\ sDone' = "nok"
            /\ rDone' = "nok"
            /\ channel' = "empty"
            /\ UNCHANGED <<sChunk, rChunk, retry>>

Done ==
    /\ sDone \in {"ok", "nok"}
    /\ UNCHANGED <<sChunk, rChunk, retry, sDone, rDone, channel>>

Next ==
    \/ Send \/ Lose \/ Deliver \/ LoseAck \/ RecvAck \/ Timeout \/ Done

DeliveryOrFailure ==
    /\ sDone = "ok" => rChunk = N
    /\ rDone = "ok" => rChunk = N

vars == <<sChunk, rChunk, retry, sDone, rDone, channel>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK DeliveryOrFailure
\* CONSTANT N = 3
\* CONSTANT MAX = 2
