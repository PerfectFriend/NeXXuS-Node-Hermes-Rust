# HOT
// magic-jetton.tact
// STRUCTURAL SKELETON — NOT compiled, NOT audited, NOT production code.
// Hands off the entrypoints + storage shape to a Tact developer via opencode.
// Standard: TON Jetton (fungible token), master + wallet contract pair.

import "@stdlib/deploy";

// ---- Jetton Master (Magic token) ----
contract MagicJettonMaster with Deployable {
    totalSupply: Int as coins;
    owner: Address;              // multisig / DAO controller, not a single EOA in prod
    jettonWalletCode: Cell;
    mintAuthority: Address;      // the backend service that credits earned Magic
    isMintPaused: Bool;

    init(owner: Address, mintAuthority: Address, jettonWalletCode: Cell) {
        self.totalSupply = 0;
        self.owner = owner;
        self.mintAuthority = mintAuthority;
        self.jettonWalletCode = jettonWalletCode;
        self.isMintPaused = false;
    }

    // Called by backend after AI-engine-verified activity (login streak,
    // reading completed, referral payout). Backend, not the LLM, is the
    // source of truth for amounts — see ai-rules-package.md.
    receive(msg: MintMagic) {
        require(sender() == self.mintAuthority, "unauthorized mint");
        require(!self.isMintPaused, "mint paused");
        require(msg.amount > 0 && msg.amount <= MAX_SINGLE_MINT, "amount out of bounds");
        self.totalSupply += msg.amount;
        // dispatch internal transfer to msg.to's jetton wallet
        // ... standard jetton mint-to-wallet message here
    }

    // Emergency circuit breaker — required before any real-value launch.
    receive(msg: SetMintPaused) {
        require(sender() == self.owner, "owner only");
        self.isMintPaused = msg.paused;
    }

    get fun totalSupply(): Int {
        return self.totalSupply;
    }
}

message MintMagic {
    to: Address;
    amount: Int as coins;
    reason: Int as uint8; // enum: 0=login,1=reading,2=referral,3=admin_adjust
}

message SetMintPaused {
    paused: Bool;
}

const MAX_SINGLE_MINT: Int = ton("50"); // sanity cap, tune before launch

// ---- Jetton Wallet (per-user balance) ----
// Standard TON Jetton wallet pattern — implement per current Jetton
// standard reference implementation at deploy time; do not hand-roll
// transfer/burn logic, use the audited reference as a base.
