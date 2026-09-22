# HOT
// auction-exchange.tact
// STRUCTURAL SKELETON — NOT compiled, NOT audited, NOT production code.
// Two mechanisms: (1) instant sell-back to a discounted pool,
// (2) peer-to-peer English auction with escrow.

import "@stdlib/deploy";

contract InstantSellPool with Deployable {
    magicJetton: Address;
    owner: Address;
    // discount vs. "floor price" oracle — prevents mint->instant-sell
    // arbitrage from silently draining the Magic supply
    discountBps: Int as uint16; // e.g. 3000 = pool pays 70% of floor

    init(owner: Address, magicJetton: Address) {
        self.owner = owner;
        self.magicJetton = magicJetton;
        self.discountBps = 3000;
    }

    receive(msg: SellToPool) {
        // 1. verify msg.sender owns the NFT (via collection lookup)
        // 2. compute payout = floorPrice(msg.rarity) * (10000 - discountBps) / 10000
        // 3. transfer NFT to pool-held burn/recycle address
        // 4. mint/transfer Magic payout to seller
    }

    get fun quote(rarity: Int): Int {
        // returns current instant-sell quote for a given rarity tier
        return 0; // placeholder — wire to floor price oracle
    }
}

message SellToPool {
    nftItem: Address;
    rarity: Int as uint8;
}

contract PeerAuction with Deployable {
    nftItem: Address;
    seller: Address;
    minBid: Int as coins;
    endTime: Int as uint32;
    highestBid: Int as coins;
    highestBidder: Address?;
    settled: Bool;
    marketplaceFeeBps: Int as uint16; // burned or routed to treasury, not to a single wallet

    init(seller: Address, nftItem: Address, minBid: Int, endTime: Int) {
        self.seller = seller;
        self.nftItem = nftItem;
        self.minBid = minBid;
        self.endTime = endTime;
        self.highestBid = 0;
        self.highestBidder = null;
        self.settled = false;
        self.marketplaceFeeBps = 250; // 2.5%
    }

    receive(msg: Bid) {
        require(now() < self.endTime, "auction ended");
        require(msg.amount > self.highestBid, "bid too low");
        // refund previous highestBidder before accepting new bid
        self.highestBid = msg.amount;
        self.highestBidder = sender();
    }

    receive(msg: Settle) {
        require(now() >= self.endTime, "auction still live");
        require(!self.settled, "already settled");
        self.settled = true;
        // transfer NFT to highestBidder (or back to seller if no bids)
        // transfer highestBid minus fee to seller; fee to treasury/burn
    }
}

message Bid {
    amount: Int as coins;
}

message Settle {
}

// ANTI-WASH-TRADING NOTE: on-chain contracts cannot see device/IP
// fingerprints. Wash-trade detection (same-cluster wallets trading with
// each other to farm volume rewards) must happen off-chain in the
// indexer/backend, then feed a denylist that this contract's settle
// path checks against before crediting any volume-based reward.
