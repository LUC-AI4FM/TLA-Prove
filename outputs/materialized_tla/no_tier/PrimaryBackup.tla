---- MODULE PrimaryBackup ----
EXTENDS Integers, Sequences, FiniteSets

CONSTANT N

VARIABLES primary, backups, pending, log

Init ==
    /\ primary = <<>>
    /\ backups = [i \in 1..N-1 |-> <<>>]
    /\ pending = <<>>
    /\ log = <<>>

Next ==
    \/ /\ pending # <<>>
        /\ primary' = Append(primary, Head(pending))
        /\ backups' = [i \in 1..N-1 |-> Append(backups[i], Head(pending))]
        /\ pending' = Tail(pending)
        /\ log' = Append(log, Head(pending))
    \/ /\ pending = <<>>
        /\ primary' = primary
        /\ backups' = backups
        /\ pending' = pending
        /\ log' = log

Spec == Init /\ [][Next]_<<primary, backups, pending, log>>

====
