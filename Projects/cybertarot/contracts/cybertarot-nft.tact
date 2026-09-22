# HOT
// cybertarot-nft.tact
// STRUCTURAL SKELETON — NOT compiled, NOT audited, NOT production code.
// Standard: TON TIP-4 NFT (collection + item contract pair).

import "@stdlib/deploy";

contract CyberTarotCollection with Deployable {
    owner: Address;                 // multisig controller
    nextItemIndex: Int as uint64;
    itemCode: Cell;                 // code for individual NFT item contracts
    mintAuthority: Address;         // backend service; mint odds enforced here, not on-chain RNG alone
    royaltyBps: Int as uint16;      // e.g. 500 = 5%, paid to creator on every resale

    init(owner: Address, mintAuthority: Address, itemCode: Cell) {
        self.owner = owner;
        self.mintAuthority = mintAuthority;
        self.itemCode = itemCode;
        self.nextItemIndex = 0;
        self.royaltyBps = 500;
    }

    // Backend calls this AFTER deducting Magic and rolling rarity
    // server-side. On-chain contract trusts mintAuthority for the roll —
    // do not re-roll rarity on-chain from block randomness alone, it's
    // manipulable by validators/miners in some designs. Use a commit-reveal
    // scheme (see note below) if fully trustless minting is required.
    receive(msg: MintCard) {
        require(sender() == self.mintAuthority, "unauthorized mint");
        require(msg.rarity >= 0 && msg.rarity <= 3, "invalid rarity"); // 0=common..3=legendary
        // deploy item contract at self.nextItemIndex with:
        //   owner = msg.to, cardId = msg.cardId, rarity = msg.rarity,
        //   soulbound = (msg.rarity == 0)  // base deck is non-transferable
        self.nextItemIndex += 1;
    }

    get fun collectionData(): CollectionData {
        return CollectionData{
            nextItemIndex: self.nextItemIndex,
            owner: self.owner,
        };
    }
}

message MintCard {
    to: Address;
    cardId: Int as uint8;     // index into the 78-card base set, or extended set id
    rarity: Int as uint8;     // 0 common(soulbound) / 1 rare / 2 epic / 3 legendary
    mintBatchRef: Int as uint64; // ties back to off-chain audit log entry
}

struct CollectionData {
    nextItemIndex: Int as uint64;
    owner: Address;
}

// ---- NFT Item ----
contract CyberTarotItem with Deployable {
    collection: Address;
    owner: Address;
    cardId: Int as uint8;
    rarity: Int as uint8;
    soulbound: Bool;

    init(collection: Address, owner: Address, cardId: Int, rarity: Int, soulbound: Bool) {
        self.collection = collection;
        self.owner = owner;
        self.cardId = cardId;
        self.rarity = rarity;
        self.soulbound = soulbound;
    }

    receive(msg: Transfer) {
        require(!self.soulbound, "soulbound: base deck cards cannot be transferred");
        require(sender() == self.owner, "owner only");
        self.owner = msg.newOwner;
    }
}

message Transfer {
    newOwner: Address;
}

// NOTE on fairness: if "provably fair" minting becomes a marketing claim,
// switch to a commit-reveal RNG scheme (server commits hash of seed before
// payment, reveals seed after, client can verify) rather than trusting
// mintAuthority blindly. Flag this decision to Tomas before launch copy
// makes any "provably fair" claim.
