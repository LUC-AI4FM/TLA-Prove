---- MODULE BoundedRetransmissionProtocol ----
EXTENDS Naturals

CONSTANTS NUM_CHUNKS, MAX_RETRIES

VARIABLES chunk, retransmit_count, channel

Init ==
    /\ chunk = 1
    /\ retransmit_count = 0
    /\ channel = {}

Send ==
    /\ channel = {}
    /\ channel' = {chunk}
    /\ retransmit_count' = retransmit_count
    /\ chunk' = chunk

Receive ==
    /\ channel # {}
    /\ chunk' = CHOOSE c \in channel : TRUE
    /\ channel' = {}
    /\ retransmit_count' = 0

Timeout ==
    /\ channel # {}
    /\ retransmit_count < MAX_RETRIES
    /\ channel' = channel
    /\ retransmit_count' = retransmit_count + 1
    /\ chunk' = chunk

GiveUp ==
    /\ channel # {}
    /\ retransmit_count = MAX_RETRIES
    /\ channel' = channel
    /\ retransmit_count' = retransmit_count
    /\ chunk' = IF chunk < NUM_CHUNKS THEN chunk + 1 ELSE 1

Next == Send \/ Receive \/ Timeout \/ GiveUp

vars == <<chunk, retransmit_count, channel>>

Spec == Init /\ [][Next]_vars

TypeOK ==
    /\ chunk \in 1..NUM_CHUNKS
    /\ retransmit_count \in 0..MAX_RETRIES
    /\ channel \subseteq 1..NUM_CHUNKS

====
