# Security Policy — NeXXus-Node-Hermes-Rust

## Reporting

RC1 re-audit (Grok, 2026-11-12, through `d69647f`): all previous Medium+
findings closed; no new Critical/High. See `docs/THREAT_MODEL.md`,
`docs/DEP-01-dependency-audit.md`, `docs/DEP-03-secret-rotation.md`,
`docs/plans/2026-11-12-post-audit-plan.md`.

## Distribution rule (DEP-03, risk accepted by owner 2026-11-12)

The **full git history of `main` contains 3 historical Telegram bot tokens**
(bot-IDs in `docs/DEP-03-secret-rotation.md`). Owner elected NOT to revoke
them. Therefore:

- **Canonical source for external auditors / public distribution is the
  squash mirror** — one commit, secret-scan clean (recipe in
  `docs/DEP-03-secret-rotation.md`). Do NOT share full history externally.
- If this repository ever becomes public, the tokens MUST be revoked via
  @BotFather and history rewritten (`git filter-repo`) first.

## CI gates

- `cargo test --workspace` (172 tests) + desktop tests (19)
- `cargo clippy --workspace --all-targets -- -D warnings`
- `cargo audit` (reads `.cargo/audit.toml`; 0 non-ignored advisories)
- proptest wire fuzz: `cargo test -p nexxus-core --test wire_fuzz`
