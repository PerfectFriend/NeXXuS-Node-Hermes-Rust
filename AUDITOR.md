# NeXXus Node — External Audit Brief (RC1)

Read `docs/audits/2026-11-11-external-audit-prep.md` first — it has the attack-surface map, the findings already fixed this session (with live PoCs), the green security probes, and the 10 questions we want you to attack hardest.

## Quick start
```bash
git clone <this repo> && cd NeXXus-Node
cargo test --workspace            # 157 tests, all green
cargo clippy --workspace --all-targets -- -D warnings   # 0 warnings
cargo build --release --bin nexxusd
NEXXUS_TOR=0 ./target/release/nexxusd /tmp/audit-store.redb
# P2P wire v3 on 0.0.0.0:4001, local WS JSON-RPC on 127.0.0.1:4010 (token in ~/.nexxus/api.token, 0600)
```

## Layout
- `crates/nexxus-core` — crypto (SLIP-10, Ed25519, AES-GCM vault, XChaCha20-Poly1305, RS/GF256, merkle), wire v3 codec, golden vectors in `tests/fixtures/`
- `crates/nexxus-econ` — economics: 16 GB sections, 56-day vesting, anti-loop invariant 1.30 > 1.25 NEXX/GB/day
- `crates/nexxus-node` — the daemon: P2P net, local API, storage, backups, seed vault, Tor (arti), CLI
- `nexxus-desktop` — Tauri monitor/guardian (tray, onboarding, Telegram alerts)

## ⚠️ Before granting access: secrets in git history
`git log --all -S` finds a GitHub PAT and bot-token mentions in history (HEAD is clean). Owner must rotate them and either filter history or share a squashed mirror. Details (no values): `docs/audits/2026-11-11-external-audit-prep.md`.

## Suggested focus order
1. Wire v3 frame handling (`net/frame.rs`, `net/network.rs`) — DoS, signature binding, announce replay.
2. Storage integrity: hash verification + nonce invariant (`storage.rs`, `at_rest.rs`).
3. Local API auth (`local_api.rs`, `api_auth.rs`).
4. Seed vault / backups (`seed_vault.rs`, `backup.rs`, `core/keys/vault.rs`).
5. Dependencies (`cargo audit`) and guardian process management (`nexxus-desktop/src-tauri/guardian.rs`).

Report format: severity (CRITICAL/HIGH/MEDIUM/LOW) + `file:line` + PoC command + suggested fix. Russian or English both fine.
