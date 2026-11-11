# NeXXus Monitor — руководство (RC1)

Монитор (`nexxus-desktop`, Tauri) управляет локальной нодой (`nexxusd`) и живёт в трее.

## Запуск
- Ярлык рабочего стола → `deploy/desktop/nexxus-desktop-launch` (или systemd user unit `nexxus-monitor.service`, `Restart=on-failure`).
- Монитор поднимает `nexxusd` сам (single-instance lock `~/.nexxus/monitor.lock`), читает адрес API из `node.conf`.

## Дашборд (9 вкладок)
1. **Обзор** — статус, NodeID (hero-поле), карточки.
2. **Нода** — конфиг (load/validate/save), systemd unit install/uninstall, stop/restart, полное отключение.
3. **Сеть** — пиры, connect, pause/resume.
4. **Хранилище** — чанки, SMP, PoR, информация о сторе.
5. **Логи** — хвост `~/.nexxus/nexxusd.log`, live-режим.
6. **Tor** — статус, onion, dial.
7. **Эпоха** — merkle root, кворум.
8. **Экономика** — секции 16 ГБ, доход/расход, анти-луп, вестинг 56 дн, health.
9. **Настройки** — Telegram (токен в `~/.nexxus/telegram.json`, 0600), **BIP39 сид** (показать/копировать/импорт), **seed.vault** (бэкап с PIN/duress-PIN, восстановление), **бэкапы стора** (создать/список/verify/staged restore), **doctor**, **selftest API**.

Все панели ходят через единую команду `node_api_cmd` → WS JSON-RPC API ноды с токеном (`~/.nexxus/api.token`).

## Безопасность
- Сид-фраза: показывается только по confirm, никогда не в логах; зашифрованный бэкап `*.seed.vault` (AES-256-GCM, PBKDF2 600k, 0600); duress-PIN → алерт в Telegram, сид не восстанавливается.
- Бэкапы стора: `~/.nexxus/backups/<name>/` + manifest (sha256, merkle). API готовит `*.restore-candidate.redb` и **никогда** не трогает живой стор; подмена — `nexxusd restore <name>` при остановленном демоне.
- `nexxusd doctor` — права 0600, шифрование at rest, идентичность, seed vault, бэкапы, проблемы.

## CLI ноды
`nexxusd init [--mnemonic …] [store]`, `id`, `status`, `peers`, `peer add/dial-onion`, `upload/download`, `logs`, `test-por`, `test-interhost`, `benchmark`, **`doctor`**, **`backup`**, **`backups`**, **`restore <name>`**.
