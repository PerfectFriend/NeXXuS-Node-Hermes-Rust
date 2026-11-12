# DEP-01 — аудит зависимостей (cargo audit)

Статус: **ВЫПОЛНЕНО 2026-11-12** (было «ручной, в sandbox нет» — cargo-audit 0.23.0
установлен, прогнан). Конфиг игноров: `.cargo/audit.toml`. CI: `cargo audit` в
каждом прогоне (шаг ниже).

## Результат сканирования

`cargo audit` → 555 крейтов в Cargo.lock, **3 уязвимости + 2 unmaintained warning**,
все транзитивные через Tor-ветку (arti-client 0.48 / tor-* 0.48):

| ID | Крейт | Версия | Откуда | Обоснование игнора |
|---|---|---|---|---|
| RUSTSEC-2023-0071 | rsa | 0.9.10 | ssh-key-fork-arti 0.6.7 → tor-key-forge/tor-llcrypto 0.48 | Marvin Attack — timing key recovery в RSA. Наш код RSA не использует (Ed25519 через ed25519-dalek); ssh-key нужен arti только для OpenSSH-konverтации ключей onion-сервиса. Форк `ssh-key-fork-arti` upstream не обновляет, semver arti 0.48 пинит rsa 0.9. |
| RUSTSEC-2026-0387 | crypto-bigint | 0.5.5 | elliptic-curve 0.13.8 → tor-llcrypto 0.48 | Timing variability в constant-time операциях. Через tor-llcrypto пинится arti 0.48 (`crypto-bigint 0.5.x` требуется жёстко); наш прямой crypto — ed25519-dalek/curve25519-dalek/chacha20poly1305, этот крейт в них не участвует. |
| RUSTSEC-2026-0459 | libsqlite3-sys | 0.38.2 | rusqlite 0.40.2 → tor-dirmgr 0.48 | CVE в bundled C SQLite. Используется только Tor-dirmgr для кэша директорий; при `NEXXUS_TOR=0` этот путь не исполняется. |
| RUSTSEC-2025-0141 | bincode | 2.0.1 | typed-index-collections → arti | unmaintained, без фикса upstream, warning-уровень. Транзитивно от arti. |
| RUSTSEC-2024-0436 | paste | 1.0.15 | fs-mistrust → arti | unmaintained proc-macro, без фикса. Транзитивно от arti. |

## Что сделано

1. arti-client + tor-rtcompat + tor-hsservice + tor-cell подняты 0.47 → **0.48**
   (последняя версия; часть advisories в 0.47 закрыта, rsa/crypto-bigint/libsqlite — нет, см. таблицу).
2. `.cargo/audit.toml` — игноры 3 уязвимостей с обоснованием (выше). Прогон:
   `cargo audit` → 0 vulnerabilities (2 allowed warnings остаются, задокументированы).
3. Сборка после апгрейда: `cargo build --workspace` чисто.

## CI шаг (добавить в pipeline)

```yaml
- run: cargo install cargo-audit --locked
- run: cargo audit   # читает .cargo/audit.toml автоматически
```

## Регрессия

При `cargo update -p arti-client` (или любой tor-*) перепрогнать `cargo audit`
и пересмотреть игноры — цель: ноль не-игнорированных advisories.
