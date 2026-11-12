# THREAT MODEL — NeXXuS-Node (RC1)

Source: external audit `AUDIT_REPORT_NeXXuS_Node_Hermes_Rust.md` §6 (2026-11-12), extended with the API trust boundary (API-02). Statuses reflect commit `532575e`+ (фаза A1 закрыта).

## Trust boundaries

1. **P2P port (0.0.0.0:4001) is public by design.**
   Protection = Ed25519 per-frame signatures after a verified `NodeAnnounce`
   (peer key bound to the connection). DoS surface is bounded by NET-01:
   `MAX_GLOBAL_CONNS=128`, per-IP `≤8 active / ≤20 new per min`,
   `HANDSHAKE_TIMEOUT=4s`, frame cap `MAX_FRAME_LEN=4 MiB` checked **before**
   allocation, `MAX_PEERS=64`, `IDLE_TIMEOUT=20min` (NET-03).
   Session nonce is **per-connection random** (NET-02) — a frame signed under
   another connection's nonce is rejected with `0x0008`.

2. **Local API (127.0.0.1:4010) trust boundary is the local Unix user.**
   Possession of `~/.nexxus/api.token` (0600, `create_new`, constant-time
   compare) = full control of the node. The API binds to loopback only.
   Fail-closed: without a successful `auth` only `ping` is answered.
   WS hardening (API-01): `max_message_size`/`max_frame_size` = 1 MiB,
   `MAX_WS_CONNECTIONS=16`, unmasked frames rejected.

3. **Seed compromise is total.**
   The duress PIN protects against coerced unlock, **not** against theft of
   the encrypted vault + offline PIN brute-force — mitigated by
   PBKDF2-HMAC-SHA256 with 600k iterations (100k legacy fallback on open).
   The at-rest store key is derived from the seed (HKDF-SHA256), so anyone
   with the seed can decrypt the whole store. Mnemonic strings are
   `Zeroizing<String>` in every path (VLT-01).

4. **Backups are copies of the encrypted store.**
   `backups/` holds `store.redb` copies + `manifest.json` (sha256, merkle
   root, chunk count). Restore never overwrites a live store: verify +
   staged candidate + `swap_backup` only with the daemon stopped, under
   exclusive flock (`BKP-01/02`). Backup names and manifest `store_file`
   are validated as plain file names (no path traversal).

5. **Wire protocol invariants.**
   - Nonce reuse is prevented by design: at-rest nonce = first 24 bytes of
     the chunk hash and `put_chunk` refuses to overwrite an existing hash
     (verifies SHA-256(data) == hash).
   - Every frame after the announce is signature-verified against the
     announced key **and** the per-connection session nonce.
   - Unknown opcodes / unauthenticated peers get explicit `ErrorResponse`
     codes (0x0006 unknown peer, 0x0007 paused, 0x0008 bad signature,
     0x0009 peer table full) and never reach the dispatcher.

## Out of scope / accepted residual risk

- `cargo audit` / `cargo deny` run in CI, not in the dev sandbox (DEP-01).
- Git history contains old secrets (3 Telegram bot tokens, см.
  `docs/DEP-03-secret-rotation.md`): **risk accepted владельцем 2026-11-12** —
  токены не ревокаются. Поэтому канонический источник для раздачи/аудита —
  squash-mirror (один коммит, скан чистый), а не полная история main.
  Если репо станет публичным — ревокация обязательна.
- Peer table eviction (RES-05 re-audit): при полном столе (MAX_PEERS=64)
  новый пир отклоняется (0x0009), честные пиры **не вытесняются** — refresh
  только двигает существующего в front bucket'а (Kademlia K=20, LRU).
  Теоретически атакующий может занять все 64 слота своими валидными
  идентичностями и не пускать новых честных пиров (eclipse-частичное
  ограничение); существующие соединения при этом не рвутся. Принято как
  residual Low — mitigations: мониторинг доли пиров, в будущем reputation/eviction.
- Economic model (16 GB sections, 56-day vesting, anti-loop invariant
  1.30 > 1.25 NEXX/GB/day) is not formally verified — design-level only.
- Tor layer (arti) reviewed at design level only; disabled via `NEXXUS_TOR=0`.
