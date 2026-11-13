# USER GUIDE — NeXXuS Node (RC1)

## Быстрый старт (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/PerfectFriend/NeXXuS-Node-Hermes-Rust/main/install.sh | bash
# или из squash-mirror (канонический артефакт раздачи, см. SECURITY.md)
nexxusd            # слушает P2P 127.0.0.1:4001, Local API 127.0.0.1:4010
```

Монитор (desktop, Tauri): `nexxus-desktop` — guardian следит за демоном,
делает автобэкапы (каждые 24 ч, ротация 5, копия на /run/media), шлёт отчёты
в Telegram.

## Переменные окружения

| Переменная | Дефолт | Смысл |
|---|---|---|
| `NEXXUS_LISTEN` | `127.0.0.1:4001` | Адрес P2P-слушателя. Наружу (`0.0.0.0:4001`) — осознанный выбор, см. THREAT_MODEL (RES-02) |
| `NEXXUS_API_LISTEN` | `127.0.0.1:4010` | Local WS API, токен в `~/.nexxus/api.token`, fail-closed |
| `NEXXUS_DATA_DIR` | `~/.nexxus` | стор, бэкапы, конфиг |
| `NEXXUS_TOR` | `0` | `1` — публикация onion-сервиса через arti |
| `NEXXUS_CONFIG_DIR` | — | переопределение каталога конфигов (тесты) |
| `GET /metrics` | API-порт, `Authorization: Bearer <api.token>` | Prometheus text: P2P-счётчики + стор (used/cap/free/chunks); без токена — 401 |
| `NEXXUS_MAX_STORE_BYTES` | `0` (без лимита) | user-defined disk cap стора; `put_chunk` отклоняет запись сверх cap и при free space < 2× размер чанка |

## Что умеет RC1

- P2P wire v3: per-connection nonce в подписи, rate limits (128 глобально, 8/IP,
  20 новых/IP/мин), handshake timeout 4 с, max peers 64, idle 20 мин
- Шифрование store at rest (двухфазная миграция, KDF 600k, duress-PIN,
  auto re-encrypt legacy vault), Zeroizing на seed/mnemonic/keys
- Бэкапы: `node_backup` / verify / restore (staging + CLI swap при остановленном
  демоне), `node_backup_delete` с `confirm: true`, автобэкап + ротация + 3-2-1
- Идентичность: BIP39, зашифрованный seed.vault, verification challenges
- Экономика и эпохи: **accounting only** — vesting 56 дней, секции 16 GB,
  health; это не on-chain и не платежи. Подписанный экспорт отчёта:
  `node_econ_export` (ed25519-подпись над canonical JSON, верифицируется pubkey ноды)
- Tor — опционально, design-level review

## Чего НЕТ (намеренно, не SIM)

- Платежи / marketplace / глобальные квоты — нет settlement-пути
- Формальная верификация эконом-модели
- FUSE/sync-folder с plaintext — threat model не позволяет
- Onion-экспоуз дашборда монитора
- Полный паритет платформ (Windows/Android — в roadmap E4)

## Безопасность

- Репортить уязвимости: см. `SECURITY.md`
- Раздача — **только squash-mirror** (история main содержит исторические
  bot-токены, risk-accepted владельцем; рецепт: `docs/DEP-03-secret-rotation.md`)
- Threat model: `docs/THREAT_MODEL.md`; серия аудитов: `docs/audits/`
- Точка входа для ревьюеров: `AUDITOR.md`
