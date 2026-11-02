# ADR-0005: Хранилище индекса — redb

**Статус:** Принят, 2026-11-02.

## Контекст
TS-демон хранит чанки как `<idx>.dat` на диске, состояние — в памяти процесса (теряется при рестарте). Нужен персистентный индекс без внешнего демона БД.

## Решение
- `crates/nexxus-node/src/store/index.rs` использует **redb** (встраиваемый, ACID, pure-Rust): таблица `chunk_hash[32] -> {file_id, chunk_index, len, created_at}`.
- Файлы чанков остаются в текущем layout `data_dir/chunks/<idx>.dat` → миграция с живого `.deb` без потери данных (`migrates_existing_chunks_dir()` тест).
- Запись: `fsync` файла чанка и commit redb **до** отправки STORE_CHUNK_ACK.

## Последствия
Зависимость `redb` только в `nexxus-node`; ядро остаётся storage-agnostic.
