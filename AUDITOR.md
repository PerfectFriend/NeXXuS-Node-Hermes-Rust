# NeXXus Node — External Audit Brief (RC1, post-hardening re-audit)

**Status:** re-audit 2026-11-12 (Grok, through `d69647f`) — all previous Medium+
findings CLOSED, no new Critical/High. Residuals are operational and
documented in `docs/THREAT_MODEL.md` §"Out of scope / accepted residual risk".

⚠️ **Access rule (DEP-03, risk accepted by owner 2026-11-12):** the full git
history of `main` contains 3 historical Telegram bot tokens. Do NOT share the
full history externally. Use the **squash mirror** (one commit, secret scan
clean — recipe in `docs/DEP-03-secret-rotation.md`).

## Quick start

```bash
git clone <squash mirror> && cd NeXXus-Node
cargo test --workspace                                  # 173 tests, green
cargo clippy --workspace --all-targets -- -D warnings   # 0 warnings
cargo audit                                             # 0 non-ignored advisories (.cargo/audit.toml)
cargo test -p nexxus-core --test wire_fuzz --test wire_vectors   # fuzz + golden vectors
cargo build --release --bin nexxusd
NEXXUS_TOR=0 ./target/release/nexxusd /tmp/audit-store.redb
# P2P wire v3 on 0.0.0.0:4001, local WS JSON-RPC on 127.0.0.1:4010
# (token in ~/.nexxus/api.token, 0600, constant-time compare, fail-closed)
```

CI gates (`.github/workflows/rust-ci.yml`): test / clippy / release build /
cargo audit / wire fuzz — all required on every PR.

## Layout

- `crates/nexxus-core` — crypto (SLIP-10, Ed25519, AES-GCM vault w/ duress-PIN,
  XChaCha20-Poly1305, RS/GF256, merkle), wire v2/v3 codec, payloads
  - tests: `tests/wire_fuzz.rs` (proptest), `tests/wire_vectors.rs` (golden,
    shared JSON in `nexxus-vectors/06_wire_frames_v2_v3.json`), `tests/fixtures/`
- `crates/nexxus-econ` — economics: 16 GB sections, 56-day vesting, saturating
  integer micro-NEXX arithmetic, anti-loop invariant 1.30 > 1.25 NEXX/GB/day
- `crates/nexxus-node` — daemon: P2P net (rate limits, per-connection nonce,
  peer cap, idle timeout), local WS API (fail-closed token auth, 1 MiB WS
  limits), encrypted-at-rest redb store (two-phase migration), verified
  backups (flock + path validation), seed vault (PBKDF2 600k, auto re-encrypt
  from legacy 100k), `doctor` self-check, Tor via arti (NEXXUS_TOR=0)
- `nexxus-desktop` — Tauri monitor/guardian: tray, onboarding, Telegram alerts,
  flock single-instance (no TOCTOU)

## Key documents

- `docs/THREAT_MODEL.md` — trust boundaries + every closed finding → mechanism
- `docs/plans/2026-11-12-post-audit-plan.md` — remediation plan with per-item status
- `docs/DEP-01-dependency-audit.md` — cargo audit run + justified ignores
- `docs/DEP-03-secret-rotation.md` — history secrets inventory + squash recipe
- `SECURITY.md` — distribution rule + CI gates
- `docs/audits/` — 2026-11-09 full review, 2026-11-11 audit prep, 2026-11-11 RC1 review

## Suggested focus order for the auditor

1. Wire v3 frame handling (`net/frame.rs`, `net/network.rs`) — DoS, signature
   binding to per-connection nonce, announce replay, peer-cap eviction (RES-05).
2. Storage integrity: SHA-256 hash check, no-overwrite, XChaCha nonce = chunk
   hash, two-phase encryption migration resume (`storage.rs`, `at_rest.rs`).
3. Local API auth (`local_api.rs`, `api_auth.rs`) — fail-closed, constant-time.
4. Seed vault / backups (`seed_vault.rs`, `backup.rs`, `core/keys/vault.rs`) —
   duress path, KDF migration, restore locks.
5. Guardian process management (`nexxus-desktop/src-tauri/guardian.rs`,
   `instance.rs` flock).
6. Econ arithmetic under hostile inputs (`nexxus-econ`) — saturating checks.

## Report format

severity (CRITICAL/HIGH/MEDIUM/LOW) + `file:line` + PoC command + suggested
fix. Russian or English both fine.
