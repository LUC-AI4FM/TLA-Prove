---- MODULE AuctionSystem ----
EXTENDS Integers
CONSTANT Max
VARIABLES currentBid, bidCount, auctionOpen

Init == currentBid = 0 /\ bidCount = 0 /\ auctionOpen = TRUE

PlaceBid == auctionOpen = TRUE /\ currentBid < Max /\ bidCount < Max
            /\ currentBid' = currentBid + 1
            /\ bidCount' = bidCount + 1
            /\ UNCHANGED auctionOpen

CloseAuction == auctionOpen = TRUE /\ bidCount > 0
                /\ auctionOpen' = FALSE
                /\ UNCHANGED <<currentBid, bidCount>>

Next == PlaceBid \/ CloseAuction
        \/ UNCHANGED <<currentBid, bidCount, auctionOpen>>

Spec == Init /\ [][Next]_<<currentBid, bidCount, auctionOpen>>

TypeOK == currentBid \in 0..Max /\ bidCount \in 0..Max
          /\ auctionOpen \in BOOLEAN

BidsBounded == bidCount <= Max /\ currentBid <= Max

SafetyInv == auctionOpen = FALSE => bidCount > 0
====
