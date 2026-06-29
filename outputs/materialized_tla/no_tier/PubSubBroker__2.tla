---- MODULE PubSubBroker ----
EXTENDS Integers, FiniteSets

CONSTANT N
ASSUME N \in 1..3

Topics == 1..N
Subs == 1..N
MaxMsgs == 1

VARIABLES subscriptions, published, delivered

TypeOK ==
    /\ subscriptions \in [Subs -> SUBSET Topics]
    /\ published \in [Topics -> 0..3]
    /\ delivered \in [Subs -> [Topics -> 0..3]]

Init ==
    /\ subscriptions = [s \in Subs |-> {}]
    /\ published = [t \in Topics |-> 0]
    /\ delivered = [s \in Subs |-> [t \in Topics |-> 0]]

Subscribe(s, t) ==
    /\ s \in Subs
    /\ t \in Topics
    /\ subscriptions' = [subscriptions EXCEPT ![s] = @ \cup {t}]
    /\ UNCHANGED <<published, delivered>>

Publish(t) ==
    /\ t \in Topics
    /\ published[t] < MaxMsgs
    /\ published' = [published EXCEPT ![t] = @ + 1]
    /\ UNCHANGED <<subscriptions, delivered>>

Deliver(s, t) ==
    /\ s \in Subs
    /\ t \in subscriptions[s]
    /\ delivered[s][t] < published[t]
    /\ delivered' = [delivered EXCEPT ![s][t] = @ + 1]
    /\ UNCHANGED <<subscriptions, published>>

Done ==
    /\ \A t \in Topics : published[t] = MaxMsgs
    /\ UNCHANGED <<subscriptions, published, delivered>>

Next ==
    \/ \E s \in Subs, t \in Topics : Subscribe(s, t)
    \/ \E t \in Topics : Publish(t)
    \/ \E s \in Subs, t \in Topics : Deliver(s, t)
    \/ Done

DeliveryGuarantee ==
    \A s \in Subs, t \in Topics :
        t \in subscriptions[s] => delivered[s][t] <= published[t]

vars == <<subscriptions, published, delivered>>
Spec == Init /\ [][Next]_vars
====

\* TLC Configuration
\* SPECIFICATION Spec
\* INVARIANT TypeOK DeliveryGuarantee
\* CONSTANT N = 2
