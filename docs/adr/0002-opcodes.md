# ADR-0002: Каноническая таблица опкодов

**Статус:** Принят, 2026-11-02.

## Контекст
Спека задаёт `0x0C = EPOCH_FINALIZE`, `0x0D = SMP_ENVELOPE`. TS-код (`src/utils/p2pWire.ts:21-35`) использует `0x0C = SMP_MESSAGE_ENVELOPE` и вообще не имеет EPOCH_FINALIZE.

## Решение (намертво)
```rust
#[repr(u8)]
pub enum Opcode {
    Ping            = 0x01,
    Pong            = 0x02,
    NodeAnnounce    = 0x03,
    StoreChunk      = 0x04,
    StoreChunkAck   = 0x05,
    FetchChunk      = 0x06,
    FetchChunkResp  = 0x07,
    PorChallenge    = 0x08,
    PorResponse     = 0x09,
    KadFindNode     = 0x0A,
    KadNodesFound   = 0x0B,
    EpochFinalize   = 0x0C,
    SmpEnvelope     = 0x0D,
    ErrorResponse   = 0xFF,
}
```
TS-значение `SMP_MESSAGE_ENVELOPE=0x0C` — баг; умирает вместе с TS-слоем в Фазе 8.

## Последствия
Значения закреплены; перестановка/удаление запрещены без bump версии протокола.
